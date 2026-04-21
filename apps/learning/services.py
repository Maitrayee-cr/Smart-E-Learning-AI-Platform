import re
from collections import Counter
from decimal import Decimal

from django.db import models
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.courses.models import Course, Quiz

from .models import CartItem, Certificate, Enrollment, LessonProgress, Result, Wishlist

AI_STOPWORDS = {
    'about',
    'after',
    'again',
    'against',
    'also',
    'an',
    'and',
    'any',
    'are',
    'because',
    'been',
    'before',
    'being',
    'between',
    'both',
    'but',
    'can',
    'course',
    'courses',
    'each',
    'for',
    'from',
    'how',
    'into',
    'its',
    'just',
    'learning',
    'more',
    'not',
    'now',
    'our',
    'out',
    'over',
    'same',
    'should',
    'smart',
    'system',
    'than',
    'that',
    'the',
    'their',
    'them',
    'then',
    'this',
    'through',
    'using',
    'very',
    'what',
    'when',
    'with',
    'your',
}

LEVEL_ORDER = {
    Course.BEGINNER: 1,
    Course.INTERMEDIATE: 2,
    Course.ADVANCED: 3,
}

LEVEL_LABELS = {
    Course.BEGINNER: 'Beginner',
    Course.INTERMEDIATE: 'Intermediate',
    Course.ADVANCED: 'Advanced',
}


@transaction.atomic
def recalculate_course_progress(enrollment: Enrollment) -> Decimal:
    total_lessons = enrollment.course.sections.aggregate(total=models.Count('lessons'))['total']
    if not total_lessons:
        enrollment.progress_percentage = Decimal('0.00')
        enrollment.save(update_fields=['progress_percentage', 'updated_at'])
        return enrollment.progress_percentage

    completed_lessons = LessonProgress.objects.filter(
        enrollment=enrollment,
        is_completed=True,
    ).count()

    percentage = Decimal((completed_lessons * 100) / total_lessons).quantize(Decimal('0.01'))
    enrollment.progress_percentage = percentage
    if percentage >= Decimal('100.00'):
        enrollment.status = Enrollment.COMPLETED
    enrollment.save(update_fields=['progress_percentage', 'status', 'updated_at'])
    return percentage


@transaction.atomic
def evaluate_quiz_submission(*, student, quiz: Quiz, answers: dict) -> Result:
    questions = list(quiz.questions.prefetch_related('options').all())
    total_questions = len(questions)
    correct_count = 0

    for question in questions:
        selected_option_id = answers.get(str(question.id))
        if not selected_option_id:
            continue
        is_correct = question.options.filter(id=selected_option_id, is_correct=True).exists()
        if is_correct:
            correct_count += 1

    score = Decimal('0.00')
    if total_questions > 0:
        score = Decimal((correct_count * 100) / total_questions).quantize(Decimal('0.01'))

    return Result.objects.create(
        student=student,
        quiz=quiz,
        total_questions=total_questions,
        correct_answers=correct_count,
        score_percentage=score,
        is_passed=score >= quiz.pass_percentage,
    )


@transaction.atomic
def issue_certificate_if_eligible(enrollment: Enrollment):
    if enrollment.progress_percentage < 100:
        return None

    # Certificate rule: student must pass at least one quiz of this course.
    has_passed_course_quiz = Result.objects.filter(
        student=enrollment.student,
        quiz__lesson__section__course=enrollment.course,
        is_passed=True,
    ).exists()
    if not has_passed_course_quiz:
        return None

    certificate, _ = Certificate.objects.get_or_create(
        enrollment=enrollment,
        defaults={'issued_at': timezone.now()},
    )
    return certificate


def _tokenize_text(*texts):
    tokens = []
    for text in texts:
        if not text:
            continue
        for token in re.findall(r'[a-zA-Z0-9]+', text.lower()):
            if len(token) < 3 or token in AI_STOPWORDS:
                continue
            tokens.append(token)
    return tokens


def _infer_preferred_level(level_counter, avg_quiz_score, completed_courses, avg_progress):
    if not level_counter:
        if completed_courses >= 3 and avg_quiz_score >= 75:
            return Course.ADVANCED
        if completed_courses >= 1 or avg_progress >= 40 or avg_quiz_score >= 60:
            return Course.INTERMEDIATE
        return Course.BEGINNER

    dominant_level = level_counter.most_common(1)[0][0]
    if dominant_level == Course.INTERMEDIATE and completed_courses >= 2 and avg_quiz_score >= 70:
        return Course.ADVANCED
    if dominant_level == Course.BEGINNER and (avg_progress >= 55 or avg_quiz_score >= 65):
        return Course.INTERMEDIATE
    return dominant_level


def build_student_learning_profile(student):
    enrollments = list(
        Enrollment.objects.filter(student=student).select_related('course__category')
    )
    wishlist_items = list(
        Wishlist.objects.filter(student=student).select_related('course__category')
    )
    cart_items = list(
        CartItem.objects.filter(student=student).select_related('course__category')
    )
    results = list(
        Result.objects.filter(student=student)
        .select_related('quiz__lesson__section__course__category')
        .order_by('-attempted_at')
    )

    category_counter = Counter()
    keyword_counter = Counter()
    level_counter = Counter()
    paid_courses = 0
    student_interest_text = ''
    if hasattr(student, 'student_profile'):
        student_interest_text = getattr(student.student_profile, 'learning_interests', '') or ''

    for enrollment in enrollments:
        weight = 5 if enrollment.status == Enrollment.COMPLETED else 3
        if float(enrollment.progress_percentage) >= 70:
            weight += 1
        course = enrollment.course
        category_counter[course.category_id] += weight
        keyword_counter.update(_tokenize_text(course.title, course.short_description, course.description))
        level_counter[course.level] += weight
        if course.price > 0:
            paid_courses += 1

    for item in wishlist_items:
        category_counter[item.course.category_id] += 2
        keyword_counter.update(_tokenize_text(item.course.title, item.course.short_description))

    for item in cart_items:
        category_counter[item.course.category_id] += 1
        keyword_counter.update(_tokenize_text(item.course.title, item.course.short_description))
        if item.course.price > 0:
            paid_courses += 1

    if student_interest_text:
        keyword_counter.update(_tokenize_text(student_interest_text))

    avg_progress = round(
        sum(float(enrollment.progress_percentage) for enrollment in enrollments) / (len(enrollments) or 1),
        2,
    )
    avg_quiz_score = round(
        sum(float(result.score_percentage) for result in results) / (len(results) or 1),
        2,
    )
    completed_courses = sum(1 for enrollment in enrollments if enrollment.status == Enrollment.COMPLETED)
    active_courses = sum(1 for enrollment in enrollments if enrollment.status == Enrollment.ACTIVE)
    preferred_level = _infer_preferred_level(level_counter, avg_quiz_score, completed_courses, avg_progress)
    prefers_free = paid_courses == 0 and bool(enrollments or wishlist_items or cart_items)

    category_name_map = {}
    for enrollment in enrollments:
        category_name_map[enrollment.course.category_id] = enrollment.course.category.name
    for item in wishlist_items:
        category_name_map[item.course.category_id] = item.course.category.name
    for item in cart_items:
        category_name_map[item.course.category_id] = item.course.category.name

    top_categories = []
    if category_counter:
        for category_id, score in category_counter.most_common(3):
            top_categories.append(
                {
                    'id': category_id,
                    'name': category_name_map.get(category_id, 'General'),
                    'score': score,
                }
            )

    top_keywords = [keyword for keyword, _ in keyword_counter.most_common(8)]

    if not enrollments and not wishlist_items and not cart_items:
        learner_stage = 'New learner'
        summary = 'Start with a beginner-friendly course and the recommendation engine will personalize your path.'
    elif completed_courses >= 2 and avg_quiz_score >= 70:
        learner_stage = 'Fast-track learner'
        summary = 'You are building strong momentum, so the engine is prioritizing higher-impact next-step courses.'
    elif avg_progress >= 45 or active_courses >= 2:
        learner_stage = 'Growing consistently'
        summary = 'Your profile shows steady activity, so the engine is balancing depth with practical next steps.'
    else:
        learner_stage = 'Exploring interests'
        summary = 'Your profile is still discovering your strongest category signals and ideal difficulty level.'

    return {
        'has_history': bool(enrollments or wishlist_items or cart_items),
        'top_categories': top_categories,
        'top_category_ids': [item['id'] for item in top_categories],
        'top_keywords': top_keywords,
        'keyword_set': set(top_keywords),
        'preferred_level': preferred_level,
        'preferred_level_label': LEVEL_LABELS[preferred_level],
        'avg_progress': avg_progress,
        'avg_quiz_score': avg_quiz_score,
        'completed_courses': completed_courses,
        'active_courses': active_courses,
        'learner_stage': learner_stage,
        'summary': summary,
        'prefers_free': prefers_free,
        'student_interest_text': student_interest_text,
    }


def _collaborative_course_boost(student, profile, course):
    student_course_ids = list(Enrollment.objects.filter(student=student).values_list('course_id', flat=True))
    if not student_course_ids:
        return 0, []

    peer_enrollments = (
        Enrollment.objects.exclude(student=student)
        .filter(
            Q(course__category_id__in=profile['top_category_ids'])
            | Q(course__level=profile['preferred_level'])
        )
        .select_related('course__category', 'student')
    )

    peer_scores = Counter()
    for enrollment in peer_enrollments:
        similarity = 0
        if enrollment.course.category_id in profile['top_category_ids']:
            similarity += 2
        if enrollment.course.level == profile['preferred_level']:
            similarity += 1
        peer_scores[enrollment.student_id] += similarity

    if not peer_scores:
        return 0, []

    top_peer_ids = [peer_id for peer_id, _ in peer_scores.most_common(8)]
    peer_course_counts = Counter(
        Enrollment.objects.filter(student_id__in=top_peer_ids)
        .exclude(course_id__in=student_course_ids)
        .values_list('course_id', flat=True)
    )
    count = peer_course_counts.get(course.id, 0)
    if count <= 0:
        return 0, []

    boost = min(count * 4, 16)
    return boost, ['Popular with learners who have a similar course history']


def _score_course_for_profile(course, profile):
    score = 20
    reasons = []

    if not profile['has_history']:
        if course.level == Course.BEGINNER:
            score += 18
            reasons.append('Beginner-friendly difficulty')
        if course.price == 0:
            score += 8
            reasons.append('Easy to start with no purchase barrier')
        if course.is_featured:
            score += 8
            reasons.append('Highlighted by the platform as a strong pick')
    else:
        for index, category_id in enumerate(profile['top_category_ids'][:3]):
            if course.category_id == category_id:
                score += [32, 20, 12][index]
                reasons.append(f"Matches your interest in {course.category.name}")
                break

        preferred_rank = LEVEL_ORDER[profile['preferred_level']]
        course_rank = LEVEL_ORDER[course.level]
        if course_rank == preferred_rank:
            score += 16
            reasons.append(f'Fits your current {LEVEL_LABELS[course.level].lower()} learning band')
        elif course_rank == preferred_rank + 1:
            score += 12
            reasons.append('Looks like a strong next-step challenge')
        elif course_rank < preferred_rank:
            score += 7
            reasons.append('Good for strengthening your foundations')

        overlap = list(
            profile['keyword_set'].intersection(
                _tokenize_text(course.title, course.short_description, course.description, course.category.name)
            )
        )
        if overlap:
            score += min(len(overlap) * 5, 15)
            reasons.append(f"Connects with topics you already explore like {', '.join(overlap[:2])}")

        if course.price == 0 and profile['prefers_free']:
            score += 6
            reasons.append('Matches your free-course learning pattern')

    avg_rating = float(getattr(course, 'avg_rating', 0) or 0)
    student_count = int(getattr(course, 'student_count', 0) or 0)
    score += min(int(avg_rating * 3), 15)
    score += min(student_count, 10)

    if course.is_featured:
        score += 6
        reasons.append('Platform momentum is high for this course')

    return min(score, 99), reasons[:3]


def get_personalized_recommendations(student, limit=4):
    profile = build_student_learning_profile(student)
    enrolled_course_ids = Enrollment.objects.filter(student=student).values_list('course_id', flat=True)

    candidate_courses = (
        Course.objects.filter(is_published=True)
        .exclude(id__in=enrolled_course_ids)
        .select_related('category', 'instructor')
        .annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
            student_count=Count('enrollments', distinct=True),
        )
    )

    scored_courses = []
    for course in candidate_courses:
        score, reasons = _score_course_for_profile(course, profile)
        collaborative_boost, collaborative_reasons = _collaborative_course_boost(student, profile, course)
        score += collaborative_boost
        if collaborative_reasons:
            reasons = reasons + collaborative_reasons
        scored_courses.append(
            {
                'course': course,
                'score': min(score, 99),
                'headline': reasons[0] if reasons else 'Balanced recommendation for your learning path',
                'reasons': reasons or ['Balanced recommendation based on course quality and difficulty'],
            }
        )

    scored_courses.sort(
        key=lambda item: (
            item['score'],
            float(getattr(item['course'], 'avg_rating', 0) or 0),
            int(getattr(item['course'], 'student_count', 0) or 0),
        ),
        reverse=True,
    )
    return scored_courses[:limit]


def build_student_ai_insights(student):
    profile = build_student_learning_profile(student)
    enrollments = list(
        Enrollment.objects.filter(student=student).select_related('course').order_by('-enrolled_at')
    )
    latest_results = list(
        Result.objects.filter(student=student)
        .select_related('quiz__lesson__section__course')
        .order_by('-attempted_at')[:5]
    )
    active_enrollments = [enrollment for enrollment in enrollments if enrollment.status == Enrollment.ACTIVE]
    completed_enrollments = [enrollment for enrollment in enrollments if enrollment.status == Enrollment.COMPLETED]
    focus_enrollment = None
    if active_enrollments:
        focus_enrollment = sorted(
            active_enrollments,
            key=lambda enrollment: float(enrollment.progress_percentage),
            reverse=True,
        )[0]

    recent_quiz_gap = next((result for result in latest_results if not result.is_passed), None)

    if not enrollments:
        headline = 'Your AI learner profile is ready.'
        summary = 'Enroll in one course to activate personalized recommendations, next-step guidance, and progress insights.'
    elif completed_enrollments and profile['avg_quiz_score'] >= 70:
        headline = 'Your learning momentum is strong.'
        summary = 'You are completing work and performing well in quizzes, so the engine is ready to suggest bigger next steps.'
    elif focus_enrollment and float(focus_enrollment.progress_percentage) >= 70:
        headline = 'You are close to your next milestone.'
        summary = f"{focus_enrollment.course.title} is nearly done, so finishing it will unlock a clearer recommendation path."
    elif recent_quiz_gap:
        headline = 'A quiz revision can boost your profile quickly.'
        summary = 'Your activity is good, but one focused revision cycle will improve both confidence and recommendation quality.'
    else:
        headline = 'Your profile is still learning your best path.'
        summary = profile['summary']

    action_items = []
    if focus_enrollment:
        action_items.append(
            f"Prioritize {focus_enrollment.course.title} because you are already at {focus_enrollment.progress_percentage}% progress."
        )
    if recent_quiz_gap:
        action_items.append(
            f"Retake {recent_quiz_gap.quiz.title} to strengthen your score profile and unlock stronger recommendations."
        )
    if profile['top_categories']:
        action_items.append(
            f"Your strongest interest signal is {profile['top_categories'][0]['name']}, so similar courses are being ranked higher."
        )
    if not action_items:
        action_items.append('Start with one beginner course and complete the quiz so the engine can calibrate your next step.')

    profile_tags = [profile['learner_stage'], f"Target level: {profile['preferred_level_label']}"]
    if profile['top_categories']:
        profile_tags.append(f"Top category: {profile['top_categories'][0]['name']}")

    return {
        'headline': headline,
        'summary': summary,
        'action_items': action_items[:3],
        'profile_tags': profile_tags,
    }


def build_course_ai_fit(student, course):
    profile = build_student_learning_profile(student)
    score, reasons = _score_course_for_profile(course, profile)

    if score >= 80:
        label = 'High AI match'
        next_step = 'This course aligns strongly with your current interests and difficulty band.'
    elif score >= 60:
        label = 'Good next step'
        next_step = 'This looks like a sensible progression course with a healthy stretch factor.'
    else:
        label = 'Exploration pick'
        next_step = 'This can broaden your profile, though it is not yet your strongest match.'

    return {
        'score': score,
        'label': label,
        'reasons': reasons or ['Recommended from course quality, difficulty, and student demand signals'],
        'next_step': next_step,
        'preferred_level_label': profile['preferred_level_label'],
    }
