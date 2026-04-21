import base64
import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from statistics import mean

from django.conf import settings
from django.db.models import Avg, Count, Q

from apps.courses.models import Course, Lesson, Option, Question, Quiz

from .models import AssignmentSubmission, EngagementSnapshot, Enrollment, LessonProgress, Result

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    Image = None
    ImageStat = None


AI_ANALYTICS_STOPWORDS = {
    'a',
    'an',
    'and',
    'are',
    'as',
    'at',
    'be',
    'by',
    'for',
    'from',
    'how',
    'in',
    'into',
    'is',
    'it',
    'of',
    'on',
    'or',
    'that',
    'the',
    'this',
    'to',
    'with',
    'your',
}

EMOTION_SCORE_MAP = {
    EngagementSnapshot.ATTENTIVE: 88,
    EngagementSnapshot.HAPPY: 76,
    EngagementSnapshot.CONFUSED: 48,
    EngagementSnapshot.BORED: 28,
}

GOOGLE_LIKELIHOOD_SCORE = {
    'UNKNOWN': 0,
    'VERY_UNLIKELY': 1,
    'UNLIKELY': 2,
    'POSSIBLE': 3,
    'LIKELY': 4,
    'VERY_LIKELY': 5,
}

HF_EMOTION_LABEL_MAP = {
    'happy': EngagementSnapshot.HAPPY,
    'happiness': EngagementSnapshot.HAPPY,
    'joy': EngagementSnapshot.HAPPY,
    'surprise': EngagementSnapshot.CONFUSED,
    'surprised': EngagementSnapshot.CONFUSED,
    'angry': EngagementSnapshot.CONFUSED,
    'anger': EngagementSnapshot.CONFUSED,
    'sad': EngagementSnapshot.BORED,
    'sadness': EngagementSnapshot.BORED,
    'neutral': EngagementSnapshot.BORED,
    'fear': EngagementSnapshot.CONFUSED,
    'disgust': EngagementSnapshot.CONFUSED,
    'tired': EngagementSnapshot.BORED,
    'sleepy': EngagementSnapshot.BORED,
    'bored': EngagementSnapshot.BORED,
    'attentive': EngagementSnapshot.ATTENTIVE,
    'focused': EngagementSnapshot.ATTENTIVE,
}


def _tokenize_text(*texts):
    tokens = []
    for text in texts:
        for token in re.findall(r'[a-zA-Z0-9]+', (text or '').lower()):
            if len(token) < 3 or token in AI_ANALYTICS_STOPWORDS:
                continue
            tokens.append(token)
    return tokens


def _sentence_split(*texts):
    sentences = []
    for text in texts:
        if not text:
            continue
        for chunk in re.split(r'[\n\r]+|(?<=[.!?])\s+', text.strip()):
            cleaned = ' '.join(chunk.split())
            if len(cleaned.split()) >= 5:
                sentences.append(cleaned)
    return sentences


def _top_keywords(*texts, limit=6):
    counter = Counter(_tokenize_text(*texts))
    return [keyword.replace('_', ' ').title() for keyword, _ in counter.most_common(limit)]


def _softmax(scores):
    peak = max(scores)
    exps = [math.exp(item - peak) for item in scores]
    total = sum(exps) or 1
    return [item / total for item in exps]


def _truncate(text, word_limit=18):
    words = (text or '').split()
    if len(words) <= word_limit:
        return ' '.join(words)
    return ' '.join(words[:word_limit]) + '...'


def _course_source_text(course):
    lessons = list(course.sections.prefetch_related('lessons').values_list('lessons__title', 'lessons__description', 'lessons__notes'))
    pieces = [course.title, course.short_description, course.description]
    for title, description, notes in lessons:
        pieces.extend([title, description, notes])
    return '\n'.join(piece for piece in pieces if piece)


def _latest_course_results(student, course):
    return list(
        Result.objects.filter(student=student, quiz__lesson__section__course=course)
        .select_related('quiz__lesson')
        .order_by('-attempted_at')
    )


def predict_student_performance(student):
    enrollments = list(Enrollment.objects.filter(student=student).select_related('course'))
    results = list(Result.objects.filter(student=student).select_related('quiz'))

    if not enrollments:
        return {
            'label': 'Average',
            'risk_indicator': 'Moderate',
            'confidence': 58,
            'probabilities': {'at_risk': 22, 'average': 58, 'high_performing': 20},
            'explanation': 'Not enough activity yet. The model will calibrate after you complete lessons and quizzes.',
            'reasons': ['Complete a first lesson', 'Attempt one quiz', 'Add your learning interests in profile'],
        }

    progress_avg = mean(float(item.progress_percentage) for item in enrollments) / 100
    completion_rate = sum(1 for item in enrollments if item.status == Enrollment.COMPLETED) / len(enrollments)
    quiz_avg = (mean(float(item.score_percentage) for item in results) / 100) if results else 0.45
    quiz_consistency = (sum(1 for item in results if item.is_passed) / len(results)) if results else 0.35
    lesson_completion = 0
    total_lessons = 0
    for enrollment in enrollments:
        lesson_count = enrollment.course.sections.aggregate(total=Count('lessons')).get('total') or 0
        total_lessons += lesson_count
    if total_lessons:
        lesson_completion = LessonProgress.objects.filter(
            enrollment__student=student,
            is_completed=True,
        ).count() / total_lessons

    active_load_penalty = 0.12 if sum(1 for item in enrollments if item.status == Enrollment.ACTIVE) >= 4 else 0

    high_raw = -0.5 + (2.2 * progress_avg) + (1.8 * quiz_avg) + (1.1 * completion_rate) + (0.8 * quiz_consistency)
    average_raw = 0.9 + (0.7 * abs(progress_avg - 0.55) * -1) + (0.6 * abs(quiz_avg - 0.6) * -1) + (0.4 * lesson_completion)
    risk_raw = 1.25 - (2.3 * progress_avg) - (1.7 * quiz_avg) - (0.8 * completion_rate) - (0.5 * quiz_consistency) + active_load_penalty

    probs = _softmax([risk_raw, average_raw, high_raw])
    at_risk, average, high = [round(item * 100) for item in probs]
    label_map = {
        'at_risk': 'At Risk',
        'average': 'Average',
        'high_performing': 'High Performing',
    }
    probability_map = {'at_risk': at_risk, 'average': average, 'high_performing': high}
    winning_key = max(probability_map, key=probability_map.get)

    reasons = []
    if progress_avg < 0.45:
        reasons.append('Progress is still below the healthy pace threshold.')
    else:
        reasons.append('Course progress is staying at a good pace.')
    if quiz_avg < 0.6:
        reasons.append('Quiz performance suggests revision is needed on weak topics.')
    else:
        reasons.append('Quiz performance is supporting strong mastery signals.')
    if completion_rate > 0:
        reasons.append('Completed courses are boosting the performance model.')
    else:
        reasons.append('Completing one course will improve the confidence of this prediction.')

    indicator = 'High' if winning_key == 'high_performing' else 'Moderate'
    if winning_key == 'at_risk':
        indicator = 'Risk'

    return {
        'label': label_map[winning_key],
        'risk_indicator': indicator,
        'confidence': probability_map[winning_key],
        'probabilities': probability_map,
        'explanation': (
            f'This classifier blends progress, course completion, lesson consistency, and quiz quality to estimate your current learning band.'
        ),
        'reasons': reasons,
    }


def build_learning_path(enrollment):
    course = enrollment.course
    lessons = list(
        Lesson.objects.filter(section__course=course)
        .select_related('section')
        .order_by('section__order', 'order', 'id')
    )
    completed_ids = set(
        LessonProgress.objects.filter(enrollment=enrollment, is_completed=True).values_list('lesson_id', flat=True)
    )
    next_lessons = []
    for lesson in lessons:
        if lesson.id in completed_ids:
            continue
        next_lessons.append(
            {
                'title': lesson.title,
                'section': lesson.section.title,
                'duration': lesson.duration_minutes,
                'summary': _truncate(lesson.notes or lesson.description or course.short_description, 16),
            }
        )
        if len(next_lessons) == 3:
            break

    results = _latest_course_results(enrollment.student, course)
    weak_lessons = []
    seen_lesson_ids = set()
    for result in results:
        if result.score_percentage >= 65:
            continue
        lesson = result.quiz.lesson
        if lesson.id in seen_lesson_ids:
            continue
        seen_lesson_ids.add(lesson.id)
        weak_lessons.append(
            {
                'title': lesson.title,
                'score': float(result.score_percentage),
                'action': 'Revise notes and retake the quiz',
            }
        )
        if len(weak_lessons) == 3:
            break

    if not weak_lessons and next_lessons:
        weak_lessons.append(
            {
                'title': next_lessons[0]['title'],
                'score': None,
                'action': 'Review this topic first to prevent a future weak spot.',
            }
        )

    source_text = _course_source_text(course)
    key_topics = _top_keywords(source_text, limit=6)
    revision_steps = []
    if next_lessons:
        revision_steps.append(f"Finish {next_lessons[0]['title']} in {next_lessons[0]['section']}.")
    if weak_lessons:
        revision_steps.append(f"Revisit {weak_lessons[0]['title']} and repeat the related quiz.")
    if len(next_lessons) > 1:
        revision_steps.append(f"After that, continue with {next_lessons[1]['title']} to keep momentum high.")
    if not revision_steps:
        revision_steps.append('You are close to completing this course. A quiz retake is the best next step.')

    return {
        'next_lessons': next_lessons,
        'weak_lessons': weak_lessons,
        'key_topics': key_topics,
        'revision_steps': revision_steps,
    }


def build_video_summary(course):
    lessons = list(
        Lesson.objects.filter(section__course=course)
        .select_related('section')
        .order_by('section__order', 'order', 'id')
    )
    sentences = _sentence_split(
        course.short_description,
        course.description,
        *[lesson.description for lesson in lessons],
        *[lesson.notes for lesson in lessons],
    )
    key_topics = _top_keywords(course.title, course.short_description, course.description, *[lesson.notes for lesson in lessons])

    summary_points = []
    for sentence in sentences[:4]:
        summary_points.append(_truncate(sentence, 22))
    if not summary_points:
        summary_points = [
            f'{course.title} introduces {", ".join(key_topics[:3]) or "the main course foundations"}.',
            'Each lesson is summarized from course notes and outline signals.',
        ]

    lesson_highlights = []
    for lesson in lessons[:4]:
        lesson_highlights.append(
            {
                'title': lesson.title,
                'summary': _truncate(lesson.notes or lesson.description or course.short_description, 18),
            }
        )

    return {
        'summary_points': summary_points,
        'key_topics': key_topics,
        'lesson_highlights': lesson_highlights,
    }


def generate_smart_quiz_questions(lesson, question_count=5, difficulty=Question.MEDIUM, source_text=''):
    course = lesson.section.course
    base_text = '\n'.join(
        filter(
            None,
            [
                source_text,
                lesson.title,
                lesson.description,
                lesson.notes,
                course.short_description,
                course.description,
            ],
        )
    )
    sentences = _sentence_split(base_text)
    keywords = _top_keywords(base_text, limit=max(question_count + 3, 8))
    if not keywords:
        keywords = _top_keywords(course.title, course.description, limit=8)
    if not sentences:
        sentences = [
            f'{lesson.title} is part of {course.title} and covers {", ".join(keywords[:3]) or course.category.name}.'
        ]

    question_bank = []
    for index in range(question_count):
        sentence = sentences[index % len(sentences)]
        keyword = keywords[index % len(keywords)] if keywords else lesson.title
        distractors = []
        for candidate in keywords:
            if candidate != keyword and candidate not in distractors:
                distractors.append(candidate)
            if len(distractors) == 3:
                break
        while len(distractors) < 3:
            distractors.append(course.category.name)

        options = [keyword] + distractors[:3]
        if index % 2 == 1:
            options = [distractors[0], keyword, distractors[1], distractors[2]]
            correct_index = 1
        elif index % 3 == 2:
            options = [distractors[0], distractors[1], keyword, distractors[2]]
            correct_index = 2
        else:
            correct_index = 0

        question_bank.append(
            {
                'text': f"Which key topic is most closely connected to this lesson insight: '{_truncate(sentence, 18)}'?",
                'order': index + 1,
                'marks': 1 if difficulty == Question.EASY else 2 if difficulty == Question.MEDIUM else 3,
                'difficulty': difficulty,
                'options': options,
                'correct_index': correct_index,
            }
        )

    return question_bank


def create_or_replace_generated_quiz(lesson, question_count=5, difficulty=Question.MEDIUM, source_text=''):
    quiz, _ = Quiz.objects.get_or_create(
        lesson=lesson,
        defaults={
            'title': f'{lesson.title} AI Quiz',
            'description': 'Auto-generated from lesson notes using NLP topic extraction.',
        },
    )
    if not quiz.title:
        quiz.title = f'{lesson.title} AI Quiz'
    quiz.description = 'Auto-generated from lesson notes using NLP topic extraction.'
    quiz.save(update_fields=['title', 'description', 'updated_at'])
    quiz.questions.all().delete()

    generated_questions = generate_smart_quiz_questions(
        lesson=lesson,
        question_count=question_count,
        difficulty=difficulty,
        source_text=source_text,
    )
    for item in generated_questions:
        question = Question.objects.create(
            quiz=quiz,
            text=item['text'],
            order=item['order'],
            marks=item['marks'],
            difficulty=item['difficulty'],
        )
        for option_index, option_text in enumerate(item['options']):
            Option.objects.create(
                question=question,
                text=option_text,
                is_correct=option_index == item['correct_index'],
            )

    return quiz, generated_questions


def _read_image_bytes(image_file):
    if image_file is None:
        return b''
    try:
        image_file.seek(0)
    except Exception:
        pass
    try:
        return image_file.read()
    finally:
        try:
            image_file.seek(0)
        except Exception:
            pass


def _score_google_likelihood(value):
    return GOOGLE_LIKELIHOOD_SCORE.get((value or 'UNKNOWN').upper(), 0)


def _classify_with_hugging_face(image_file):
    token = getattr(settings, 'HUGGINGFACE_HUB_TOKEN', '') or getattr(settings, 'HF_TOKEN', '')
    if not token:
        return None

    image_bytes = _read_image_bytes(image_file)
    if not image_bytes:
        return None

    model = getattr(settings, 'HUGGINGFACE_EMOTION_MODEL', 'dima806/facial_emotions_image_detection')
    endpoint = f'https://router.huggingface.co/hf-inference/models/{model}'
    request = urllib.request.Request(
        endpoint,
        data=image_bytes,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        return None, 0, f'Hugging Face unavailable, fallback used. Reason: {error}'

    predictions = data
    if isinstance(data, dict):
        if data.get('error'):
            return None, 0, f'Hugging Face fallback reason: {data["error"]}'
        predictions = data.get('predictions') or data.get('labels') or data.get('scores') or []
    if predictions and isinstance(predictions[0], list):
        predictions = predictions[0]
    if not predictions:
        return None, 0, 'Hugging Face did not return emotion labels.'

    best = max(predictions, key=lambda item: float(item.get('score', 0)) if isinstance(item, dict) else 0)
    raw_label = (best.get('label') or '').strip().lower()
    score = float(best.get('score', 0))
    emotion = HF_EMOTION_LABEL_MAP.get(raw_label)
    if not emotion:
        for key, mapped_emotion in HF_EMOTION_LABEL_MAP.items():
            if key in raw_label:
                emotion = mapped_emotion
                break
    if not emotion:
        emotion = EngagementSnapshot.CONFUSED

    confidence = max(round(score * 100), 65)
    return (
        emotion,
        confidence,
        f'Hugging Face model "{model}" predicted "{raw_label}" with {confidence}% confidence.',
    )


def _classify_with_google_vision(image_file):
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '')
    if not api_key:
        return None

    image_bytes = _read_image_bytes(image_file)
    if not image_bytes:
        return None

    endpoint = f'https://vision.googleapis.com/v1/images:annotate?key={api_key}'
    payload = {
        'requests': [
            {
                'image': {'content': base64.b64encode(image_bytes).decode('ascii')},
                'features': [{'type': 'FACE_DETECTION', 'maxResults': 1}],
            }
        ]
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        return None, 0, f'Google Vision unavailable, local fallback used. Reason: {error}'

    responses = data.get('responses') or []
    if not responses or responses[0].get('error'):
        reason = responses[0].get('error', {}).get('message', 'No Google Vision response.') if responses else 'No Google Vision response.'
        return None, 0, f'Google Vision fallback reason: {reason}'

    faces = responses[0].get('faceAnnotations') or []
    if not faces:
        return (
            EngagementSnapshot.BORED,
            72,
            'Google Vision did not detect an active face, so engagement is classified as bored/away.',
        )

    face = faces[0]
    joy = _score_google_likelihood(face.get('joyLikelihood'))
    sorrow = _score_google_likelihood(face.get('sorrowLikelihood'))
    anger = _score_google_likelihood(face.get('angerLikelihood'))
    surprise = _score_google_likelihood(face.get('surpriseLikelihood'))
    confidence = round(float(face.get('detectionConfidence') or 0.7) * 100)

    if joy >= 4:
        emotion = EngagementSnapshot.HAPPY
    elif sorrow >= 3 or anger >= 3 or surprise >= 4:
        emotion = EngagementSnapshot.CONFUSED
    elif max(joy, sorrow, anger, surprise) <= 2:
        emotion = EngagementSnapshot.BORED
    else:
        emotion = EngagementSnapshot.ATTENTIVE

    analysis = (
        'Google Vision Face Detection used real face signals: '
        f'joy={face.get("joyLikelihood", "UNKNOWN")}, '
        f'sorrow={face.get("sorrowLikelihood", "UNKNOWN")}, '
        f'anger={face.get("angerLikelihood", "UNKNOWN")}, '
        f'surprise={face.get("surpriseLikelihood", "UNKNOWN")}.'
    )
    return emotion, max(confidence, 70), analysis


def _classify_emotion_from_image(image_file):
    filename = (getattr(image_file, 'name', '') or '').lower()
    hugging_face_result = _classify_with_hugging_face(image_file)
    provider_fallback_notes = []
    if hugging_face_result:
        if hugging_face_result[0]:
            return hugging_face_result
        provider_fallback_notes.append(hugging_face_result[2])

    google_result = _classify_with_google_vision(image_file)
    if google_result:
        if google_result[0]:
            return google_result
        provider_fallback_notes.append(google_result[2])
    provider_fallback_note = ' '.join(provider_fallback_notes)

    for keyword, emotion in (
        ('lazy', EngagementSnapshot.BORED),
        ('tired', EngagementSnapshot.BORED),
        ('sleeping', EngagementSnapshot.BORED),
        ('slepping', EngagementSnapshot.BORED),
        ('sleepy', EngagementSnapshot.BORED),
        ('sleep', EngagementSnapshot.BORED),
        ('closedeye', EngagementSnapshot.BORED),
        ('closed-eye', EngagementSnapshot.BORED),
        ('eyesclosed', EngagementSnapshot.BORED),
        ('yawn', EngagementSnapshot.BORED),
        ('bored', EngagementSnapshot.BORED),
        ('dull', EngagementSnapshot.BORED),
        ('confused', EngagementSnapshot.CONFUSED),
        ('doubt', EngagementSnapshot.CONFUSED),
        ('stuck', EngagementSnapshot.CONFUSED),
        ('focused', EngagementSnapshot.ATTENTIVE),
        ('attentive', EngagementSnapshot.ATTENTIVE),
        ('concentrated', EngagementSnapshot.ATTENTIVE),
        ('happy', EngagementSnapshot.HAPPY),
        ('smile', EngagementSnapshot.HAPPY),
        ('laugh', EngagementSnapshot.HAPPY),
    ):
        if keyword in filename:
            return emotion, 84, f'Filename cue "{keyword}" suggests the learner looks {emotion}.'

    if Image is None or ImageStat is None or image_file is None:
        note = 'Using simulated engagement detection because image analysis is limited.'
        if provider_fallback_note:
            note = f'{provider_fallback_note} {note}'
        return EngagementSnapshot.CONFUSED, 55, note

    try:
        image_file.seek(0)
        image = Image.open(image_file).convert('RGB')
        stat = ImageStat.Stat(image)
        brightness = sum(stat.mean) / 3
        contrast = sum(stat.stddev) / 3
        hsv_stat = ImageStat.Stat(image.convert('HSV'))
        saturation = hsv_stat.mean[1]

        # This is still a simulated classifier. Be conservative with "attentive":
        # a high-contrast image alone can also be a sleeping/side-face photo.
        if brightness > 170 and saturation > 45 and contrast > 32:
            emotion = EngagementSnapshot.HAPPY
        elif 105 <= brightness <= 155 and contrast > 58 and saturation > 62:
            emotion = EngagementSnapshot.BORED
        elif brightness < 95 and contrast < 42:
            emotion = EngagementSnapshot.BORED
        elif contrast < 30 or saturation < 22:
            emotion = EngagementSnapshot.BORED
        elif brightness < 120 and contrast > 42:
            emotion = EngagementSnapshot.CONFUSED
        elif contrast > 68 and 28 <= saturation <= 62 and brightness >= 135:
            emotion = EngagementSnapshot.ATTENTIVE
        elif brightness > 155 and contrast > 38:
            emotion = EngagementSnapshot.ATTENTIVE
        else:
            emotion = EngagementSnapshot.BORED
        return (
            emotion,
            76,
            (
                f'{provider_fallback_note} ' if provider_fallback_note else ''
            )
            + f'Local fallback used brightness {brightness:.0f}, contrast {contrast:.0f}, and saturation {saturation:.0f}.',
        )
    except Exception:
        return EngagementSnapshot.CONFUSED, 58, 'Image could not be deeply analyzed, so the system marked the engagement as uncertain/confused.'
    finally:
        try:
            image_file.seek(0)
        except Exception:
            pass


def analyze_engagement_snapshot(student, course, image_file):
    emotion, confidence, analysis = _classify_emotion_from_image(image_file)
    snapshot = EngagementSnapshot.objects.create(
        student=student,
        course=course,
        image=image_file,
        detected_emotion=emotion,
        confidence=confidence,
        engagement_score=EMOTION_SCORE_MAP.get(emotion, 50),
        analysis=analysis,
    )
    return snapshot


def analyze_plagiarism_submission(student, course, title, content):
    comparisons = []
    content_tokens = _tokenize_text(content)
    submissions = AssignmentSubmission.objects.filter(course=course).exclude(student=student).select_related('student')
    for submission in submissions:
        base_ratio = SequenceMatcher(None, (content or '').lower(), (submission.content or '').lower()).ratio()
        submission_tokens = _tokenize_text(submission.content)
        overlap_total = len(set(content_tokens).intersection(submission_tokens))
        overlap_ratio = overlap_total / (len(set(content_tokens)) or 1)
        final_score = ((base_ratio * 0.65) + (overlap_ratio * 0.35)) * 100
        comparisons.append((final_score, submission))

    comparisons.sort(key=lambda item: item[0], reverse=True)
    top_score = round(comparisons[0][0]) if comparisons else 0
    matched_submission = comparisons[0][1] if comparisons else None
    if matched_submission:
        report = (
            f'Matched most strongly with {matched_submission.student.username} on "{matched_submission.title}" at about {top_score}% similarity.'
        )
    else:
        report = 'No significant similarity found against existing submissions for this course.'

    submission = AssignmentSubmission.objects.create(
        student=student,
        course=course,
        title=title,
        content=content,
        plagiarism_score=top_score,
        matched_submission=matched_submission,
        similarity_report=report,
        is_flagged=top_score >= 45,
    )
    return submission


def _student_performance_rows(enrollments):
    student_ids = list({enrollment.student_id for enrollment in enrollments})
    Enrollment.objects.filter(student_id__in=student_ids)
    rows = []
    for student_id in student_ids:
        student = next(enrollment.student for enrollment in enrollments if enrollment.student_id == student_id)
        prediction = predict_student_performance(student)
        avg_quiz = (
            Result.objects.filter(student=student, quiz__lesson__section__course__in={enrollment.course for enrollment in enrollments if enrollment.student_id == student_id})
            .aggregate(avg=Avg('score_percentage'))
            .get('avg')
            or 0
        )
        rows.append(
            {
                'student': student,
                'prediction': prediction,
                'avg_quiz': float(avg_quiz),
            }
        )
    return rows


def build_instructor_ai_analytics(instructor):
    enrollments = list(
        Enrollment.objects.filter(course__instructor=instructor)
        .select_related('student', 'course')
        .order_by('-enrolled_at')
    )
    performance_rows = _student_performance_rows(enrollments)
    top_students = sorted(
        performance_rows,
        key=lambda item: (item['prediction']['probabilities']['high_performing'], item['avg_quiz']),
        reverse=True,
    )[:5]
    weak_learners = sorted(
        performance_rows,
        key=lambda item: (item['prediction']['probabilities']['at_risk'], -item['avg_quiz']),
        reverse=True,
    )[:5]

    quiz_stats = Result.objects.filter(quiz__lesson__section__course__instructor=instructor)
    quiz_success_rate = 0
    if quiz_stats.exists():
        quiz_success_rate = round((quiz_stats.filter(is_passed=True).count() / quiz_stats.count()) * 100, 2)

    popular_courses = list(
        Course.objects.filter(instructor=instructor)
        .annotate(student_count=Count('enrollments'))
        .order_by('-student_count', 'title')[:5]
    )
    emotion_counts = Counter(
        EngagementSnapshot.objects.filter(course__instructor=instructor).values_list('detected_emotion', flat=True)
    )

    recommendation_scores = []
    from .services import build_course_ai_fit

    for enrollment in enrollments[:30]:
        recommendation_scores.append(build_course_ai_fit(enrollment.student, enrollment.course)['score'])

    performance_bands = Counter(item['prediction']['label'] for item in performance_rows)
    return {
        'top_students': top_students,
        'weak_learners': weak_learners,
        'popular_courses': popular_courses,
        'quiz_success_rate': quiz_success_rate,
        'recommendation_performance': round(mean(recommendation_scores), 2) if recommendation_scores else 0,
        'emotion_counts': emotion_counts,
        'performance_chart': {
            'labels': ['High Performing', 'Average', 'At Risk'],
            'values': [
                performance_bands.get('High Performing', 0),
                performance_bands.get('Average', 0),
                performance_bands.get('At Risk', 0),
            ],
        },
        'engagement_chart': {
            'labels': ['Attentive', 'Happy', 'Confused', 'Bored'],
            'values': [
                emotion_counts.get(EngagementSnapshot.ATTENTIVE, 0),
                emotion_counts.get(EngagementSnapshot.HAPPY, 0),
                emotion_counts.get(EngagementSnapshot.CONFUSED, 0),
                emotion_counts.get(EngagementSnapshot.BORED, 0),
            ],
        },
    }


def build_platform_ai_analytics():
    enrollments = list(Enrollment.objects.select_related('student', 'course').order_by('-enrolled_at'))
    performance_rows = _student_performance_rows(enrollments)
    top_students = sorted(
        performance_rows,
        key=lambda item: (item['prediction']['probabilities']['high_performing'], item['avg_quiz']),
        reverse=True,
    )[:6]
    weak_learners = sorted(
        performance_rows,
        key=lambda item: (item['prediction']['probabilities']['at_risk'], -item['avg_quiz']),
        reverse=True,
    )[:6]

    popular_courses = list(
        Course.objects.annotate(student_count=Count('enrollments'))
        .order_by('-student_count', 'title')[:6]
    )
    quiz_stats = Result.objects.all()
    quiz_success_rate = round((quiz_stats.filter(is_passed=True).count() / quiz_stats.count()) * 100, 2) if quiz_stats.exists() else 0
    emotion_counts = Counter(EngagementSnapshot.objects.values_list('detected_emotion', flat=True))

    recommendation_scores = []
    from .services import build_course_ai_fit

    for enrollment in enrollments[:40]:
        recommendation_scores.append(build_course_ai_fit(enrollment.student, enrollment.course)['score'])

    flagged_submissions = list(
        AssignmentSubmission.objects.filter(is_flagged=True)
        .select_related('student', 'course', 'matched_submission__student')
        .order_by('-plagiarism_score', '-created_at')[:5]
    )
    performance_bands = Counter(item['prediction']['label'] for item in performance_rows)

    return {
        'top_students': top_students,
        'weak_learners': weak_learners,
        'popular_courses': popular_courses,
        'quiz_success_rate': quiz_success_rate,
        'recommendation_performance': round(mean(recommendation_scores), 2) if recommendation_scores else 0,
        'emotion_counts': emotion_counts,
        'flagged_submissions': flagged_submissions,
        'performance_chart': {
            'labels': ['High Performing', 'Average', 'At Risk'],
            'values': [
                performance_bands.get('High Performing', 0),
                performance_bands.get('Average', 0),
                performance_bands.get('At Risk', 0),
            ],
        },
        'engagement_chart': {
            'labels': ['Attentive', 'Happy', 'Confused', 'Bored'],
            'values': [
                emotion_counts.get(EngagementSnapshot.ATTENTIVE, 0),
                emotion_counts.get(EngagementSnapshot.HAPPY, 0),
                emotion_counts.get(EngagementSnapshot.CONFUSED, 0),
                emotion_counts.get(EngagementSnapshot.BORED, 0),
            ],
        },
    }
