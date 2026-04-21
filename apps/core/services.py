import re

from django.db.models import Avg, Count, Q
from django.urls import reverse

from apps.courses.models import Category, Course, Quiz
from apps.learning.ai_features import build_learning_path, build_video_summary, predict_student_performance
from apps.learning.models import CartItem, Certificate, Enrollment, Wishlist
from apps.learning.services import get_personalized_recommendations

from .models import FAQ

CHATBOT_STOPWORDS = {
    'a',
    'an',
    'and',
    'are',
    'about',
    'can',
    'course',
    'courses',
    'do',
    'for',
    'get',
    'help',
    'how',
    'i',
    'in',
    'is',
    'me',
    'my',
    'of',
    'on',
    'or',
    'please',
    'show',
    'tell',
    'the',
    'to',
    'what',
    'with',
    'you',
}

TOPIC_ALIASES = {
    'ai': ['artificial', 'intelligence', 'machine', 'learning', 'deep', 'learning'],
    'artificial intelligence': ['ai', 'machine', 'learning', 'deep', 'learning'],
    'ml': ['machine', 'learning', 'supervised', 'learning', 'deep', 'learning'],
    'machine learning': ['ml', 'machine', 'learning', 'supervised', 'learning', 'deep', 'learning'],
    'deep learning': ['deep', 'learning', 'ai', 'machine', 'learning'],
    'python': ['python', 'programming', 'data', 'analysis'],
    'java': ['java', 'programming'],
    'web development': ['web', 'development', 'django', 'html', 'css', 'javascript', 'full', 'stack'],
    'full stack': ['full', 'stack', 'web', 'development', 'django', 'javascript'],
    'frontend': ['html', 'css', 'javascript', 'web', 'development'],
    'html': ['html', 'css', 'javascript', 'web'],
    'css': ['css', 'html', 'javascript', 'web'],
    'javascript': ['javascript', 'html', 'css', 'web'],
    'django': ['django', 'python', 'web', 'development'],
    'database': ['dbms', 'sql', 'database'],
    'dbms': ['dbms', 'sql', 'database'],
    'sql': ['sql', 'dbms', 'database'],
    'dsa': ['data', 'structures', 'algorithms', 'cpp', 'programming'],
    'data structures': ['data', 'structures', 'algorithms', 'cpp', 'programming'],
    'cyber security': ['cyber', 'security', 'ethical', 'hacking', 'network', 'security'],
    'cybersecurity': ['cyber', 'security', 'ethical', 'hacking', 'network', 'security'],
    'ethical hacking': ['ethical', 'hacking', 'cyber', 'security'],
    'network security': ['network', 'security', 'cyber', 'security'],
    'data science': ['data', 'science', 'analysis', 'python', 'machine', 'learning'],
    'aptitude': ['aptitude', 'reasoning', 'quantitative', 'verbal'],
    'reasoning': ['reasoning', 'aptitude', 'logical', 'verbal'],
}


def _tokenize(text):
    return [
        token
        for token in re.findall(r'[a-zA-Z0-9]+', (text or '').lower())
        if len(token) > 1 and token not in CHATBOT_STOPWORDS
    ]


def _matches_any_phrase(message, phrases):
    normalized = f" {(message or '').strip().lower()} "
    return any(f" {phrase.lower()} " in normalized for phrase in phrases)


def _expand_query_tokens(message):
    normalized = (message or '').strip().lower()
    expanded_tokens = list(_tokenize(normalized))
    for phrase, aliases in TOPIC_ALIASES.items():
        if phrase in normalized:
            expanded_tokens.extend(aliases)
    return list(dict.fromkeys(expanded_tokens))


def _build_course_cards(courses):
    cards = []
    for course in courses:
        cards.append(
            {
                'title': course.title,
                'meta': f"{course.category.name} | {course.get_level_display()} | {'Free' if course.price == 0 else f'Rs. {course.price:.2f}'}",
                'url': reverse('courses:course_detail', kwargs={'slug': course.slug}),
            }
        )
    return cards


def _match_courses_from_message(message, limit=3):
    normalized = (message or '').strip().lower()
    tokens = _expand_query_tokens(message)
    if not tokens:
        return []

    query = Q()
    for token in tokens[:6]:
        query |= Q(title__icontains=token)
        query |= Q(short_description__icontains=token)
        query |= Q(description__icontains=token)
        query |= Q(category__name__icontains=token)

    candidate_courses = list(
        Course.objects.filter(is_published=True)
        .select_related('category', 'instructor')
        .filter(query)
        .distinct()
    )

    scored_courses = []
    for course in candidate_courses:
        score = _score_course_for_query(course, normalized, tokens)
        if score > 0:
            scored_courses.append((score, course))

    scored_courses.sort(key=lambda item: item[0], reverse=True)
    return [course for _, course in scored_courses[:limit]]


def _score_course_for_query(course, normalized, tokens):
    title = course.title.lower()
    category_name = course.category.name.lower()
    short_description = (course.short_description or '').lower()
    description = (course.description or '').lower()

    score = 0
    for token in tokens:
        if token in title:
            score += 10
        if token in category_name:
            score += 6
        if token in short_description:
            score += 4
        if token in description:
            score += 2

    for phrase in TOPIC_ALIASES:
        if phrase in normalized:
            if phrase in title:
                score += 18
            if phrase in category_name:
                score += 14

    return score


def _match_faq(message):
    tokens = set(_tokenize(message))
    best_faq = None
    best_score = 0
    for faq in FAQ.objects.filter(is_active=True):
        faq_tokens = set(_tokenize(faq.question + ' ' + faq.answer))
        score = len(tokens.intersection(faq_tokens))
        if score > best_score:
            best_faq = faq
            best_score = score
    return best_faq if best_score > 0 else None


def _featured_courses(limit=3):
    return list(
        Course.objects.filter(is_published=True, is_featured=True)
        .select_related('category', 'instructor')[:limit]
    )


def _free_courses(limit=3):
    return list(
        Course.objects.filter(is_published=True, price=0)
        .select_related('category', 'instructor')
        .order_by('-created_at')[:limit]
    )


def _top_categories(limit=4):
    return list(
        Category.objects.filter(is_active=True)
        .annotate(course_count=Count('courses'))
        .order_by('-course_count', 'name')[:limit]
    )


def _compact_text(text):
    return ' '.join((text or '').split()).strip()


def _build_course_learning_explanation(course):
    summary_parts = []
    short_description = _compact_text(course.short_description)
    description = _compact_text(course.description)

    if short_description:
        summary_parts.append(short_description)
    if description and description != short_description:
        summary_parts.append(description)

    lesson_titles = list(
        course.sections.values_list('lessons__title', flat=True)
    )
    lesson_titles = [title for title in lesson_titles if title][:3]
    if lesson_titles:
        summary_parts.append('Key lesson areas include ' + ', '.join(lesson_titles) + '.')

    combined = ' '.join(summary_parts).strip()
    if not combined:
        return f'{course.title} is part of your active learning path.'
    return combined


def _build_student_course_query_reply(user, message):
    normalized = (message or '').strip().lower()
    query_tokens = _expand_query_tokens(message)
    matched_courses = _match_courses_from_message(message, limit=5)
    recommendations = get_personalized_recommendations(user, limit=12)
    recommendation_map = {item['course'].id: item for item in recommendations}

    student_enrollments = list(
        Enrollment.objects.filter(student=user).select_related('course__category').order_by('-enrolled_at')
    )
    enrolled_ids = {enrollment.course_id for enrollment in student_enrollments}
    wishlist_ids = set(Wishlist.objects.filter(student=user).values_list('course_id', flat=True))
    cart_ids = set(CartItem.objects.filter(student=user).values_list('course_id', flat=True))
    relevant_history = []
    for enrollment in student_enrollments:
        relevance_score = _score_course_for_query(enrollment.course, normalized, query_tokens)
        if relevance_score > 0:
            relevant_history.append((relevance_score, enrollment))
    relevant_history.sort(key=lambda item: item[0], reverse=True)

    if not matched_courses and recommendations:
        top_recommendations = recommendations[:4]
        if relevant_history:
            top_history = relevant_history[0][1]
            reply = (
                f'Because you already took {top_history.course.title} and are at {top_history.progress_percentage}% progress there, '
                f'I ranked the strongest next courses connected to that learning path.'
            )
        elif student_enrollments:
            current_courses = ', '.join(enrollment.course.title for enrollment in student_enrollments[:2])
            reply = (
                f'You have not taken this topic yet, so I used your current courses like {current_courses} '
                'to rank the strongest next options for your profile.'
            )
        else:
            reply = (
                f'I could not find a direct catalog match for "{message}", so I ranked the strongest next courses for your current learning profile.'
            )
        return {
            'reply': reply,
            'chips': ['My progress', 'Show free courses', 'How certificates work'],
            'links': [{'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')}],
            'cards': [
                {
                    'title': item['course'].title,
                    'meta': f"{item['score']}% AI match | {item['headline']}",
                    'url': reverse('courses:course_detail', kwargs={'slug': item['course'].slug}),
                }
                for item in top_recommendations
            ],
        }

    if not matched_courses:
        return None

    cards = []
    enrolled_matches = []
    for course in matched_courses:
        personalized = recommendation_map.get(course.id)
        status_parts = []
        if course.id in enrolled_ids:
            status_parts.append('Already enrolled')
            enrolled_matches.append(course.title)
        elif course.id in cart_ids:
            status_parts.append('In cart')
        elif course.id in wishlist_ids:
            status_parts.append('In wishlist')

        if personalized:
            status_parts.append(f"{personalized['score']}% AI match")
            status_parts.append(personalized['headline'])

        status_parts.append(course.get_level_display())
        status_parts.append(course.category.name)

        cards.append(
            {
                'title': course.title,
                'meta': ' | '.join(status_parts),
                'url': reverse('courses:course_detail', kwargs={'slug': course.slug}),
            }
        )

    if enrolled_matches:
        reply = (
            'I found course matches for your question. You are already enrolled in '
            + ', '.join(enrolled_matches[:2])
            + ', so you may want to continue those first or compare them with the other matches below.'
        )
    elif relevant_history:
        top_history = relevant_history[0][1]
        related_taken = [item[1].course.title for item in relevant_history[:2]]
        reply = (
            f'Because you already took {", ".join(related_taken)}'
            f' and your strongest related course is {top_history.course.title} at {top_history.progress_percentage}% progress, '
            'these are the best next course matches for you.'
        )
    elif student_enrollments:
        current_courses = ', '.join(enrollment.course.title for enrollment in student_enrollments[:2])
        reply = (
            f'You have not taken this topic yet, so I matched it against your overall learning profile from {current_courses}. '
            'These are the best next course options for you.'
        )
    else:
        reply = 'These are the best course matches for your question based on the topic and your student learning profile.'

    return {
        'reply': reply,
        'chips': ['My progress', 'Show free courses', 'Recommend courses'],
        'links': [
            {'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')},
            {'label': 'My Learning', 'url': reverse('learning:my_learning')},
        ],
        'cards': cards,
    }


def _student_progress_reply(user):
    enrollments = list(
        Enrollment.objects.filter(student=user).select_related('course').order_by('-enrolled_at')
    )
    if not enrollments:
        return {
            'reply': 'You have not enrolled in any course yet. Start with the catalog and I can recommend a good first course.',
            'chips': ['Recommend courses', 'Show free courses', 'How certificates work'],
            'links': [{'label': 'Browse Courses', 'url': reverse('courses:course_list')}],
        }

    active_count = sum(1 for item in enrollments if item.status == Enrollment.ACTIVE)
    completed_count = sum(1 for item in enrollments if item.status == Enrollment.COMPLETED)
    avg_progress = round(sum(float(item.progress_percentage) for item in enrollments) / len(enrollments), 2)
    focus_course = max(enrollments, key=lambda item: float(item.progress_percentage))
    return {
        'reply': (
            f'You are enrolled in {len(enrollments)} courses with {active_count} active and {completed_count} completed. '
            f'Your average progress is {avg_progress}%, and your strongest current course is {focus_course.course.title} '
            f'at {focus_course.progress_percentage}% progress.'
        ),
        'chips': ['Recommend courses', 'Certificates', 'Payment history'],
        'links': [
            {'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')},
            {'label': 'My Learning', 'url': reverse('learning:my_learning')},
        ],
    }


def _build_student_learning_guidance_reply(user, message):
    normalized = (message or '').strip().lower()
    query_tokens = _expand_query_tokens(message)
    current_learning_phrases = [
        'what am i learning',
        'what am i studying',
        'which course am i learning',
        'which course am i taking',
        'my current course',
        'my current courses',
        'what should i study',
        'what should i learn now',
        'which course should i continue',
        'what should i continue',
        'continue learning',
        'what am i doing now',
    ]
    enrollments = list(
        Enrollment.objects.filter(student=user).select_related('course__category').order_by('-enrolled_at')
    )
    if not enrollments:
        return None

    active_enrollments = [enrollment for enrollment in enrollments if enrollment.status == Enrollment.ACTIVE]
    completed_enrollments = [enrollment for enrollment in enrollments if enrollment.status == Enrollment.COMPLETED]
    focus_enrollment = None
    if active_enrollments:
        focus_enrollment = max(active_enrollments, key=lambda enrollment: float(enrollment.progress_percentage))
    elif completed_enrollments:
        focus_enrollment = completed_enrollments[0]
    else:
        focus_enrollment = enrollments[0]

    if _matches_any_phrase(normalized, current_learning_phrases):
        active_titles = [enrollment.course.title for enrollment in active_enrollments[:3]]
        if active_titles:
            reply = (
                'You are currently learning '
                + ', '.join(active_titles)
                + f'. The best course to continue right now is {focus_enrollment.course.title} because it is your current focus.'
            )
        else:
            reply = (
                f'You do not have an active course right now, but your latest completed learning path includes {focus_enrollment.course.title}.'
            )
        return {
            'reply': reply,
            'chips': ['My progress', 'Recommend courses', 'How certificates work'],
            'links': [
                {'label': 'My Learning', 'url': reverse('learning:my_learning')},
                {'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')},
            ],
            'cards': [
                {
                    'title': enrollment.course.title,
                    'meta': f"{enrollment.status.title()} | {enrollment.progress_percentage}% progress | {enrollment.course.category.name}",
                    'url': reverse('learning:enrolled_course_detail', kwargs={'slug': enrollment.course.slug}),
                }
                for enrollment in (active_enrollments[:3] or [focus_enrollment])
            ],
        }

    matched_active = []
    for enrollment in active_enrollments:
        score = _score_course_for_query(enrollment.course, normalized, query_tokens)
        if score > 0:
            matched_active.append((score, enrollment))
    matched_active.sort(key=lambda item: item[0], reverse=True)

    if matched_active:
        top_match = matched_active[0][1]
        other_matches = [item[1] for item in matched_active[1:3]]
        reply = (
            f'From the courses you are currently learning, {top_match.course.title} is the closest match to your question and you are at '
            f'{top_match.progress_percentage}% progress there.'
        )
        explanation = _build_course_learning_explanation(top_match.course)
        if explanation:
            reply += f' In that course, you are learning: {explanation}'
        if other_matches:
            reply += ' Other related active courses are ' + ', '.join(item.course.title for item in other_matches) + '.'
        return {
            'reply': reply,
            'chips': ['My progress', 'Recommend courses', 'Quiz help'],
            'links': [
                {'label': 'My Learning', 'url': reverse('learning:my_learning')},
                {'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')},
            ],
            'cards': [
                {
                    'title': enrollment.course.title,
                    'meta': f"Active | {enrollment.progress_percentage}% progress | {enrollment.course.category.name}",
                    'url': reverse('learning:enrolled_course_detail', kwargs={'slug': enrollment.course.slug}),
                }
                for _, enrollment in matched_active[:3]
            ],
        }

    return None


def build_chatbot_response(message, user):
    normalized = (message or '').strip()
    lower_message = normalized.lower()
    tokens = set(_tokenize(normalized))
    is_student = user.is_authenticated and getattr(user, 'role', '') == 'student'

    if not normalized:
        return {
            'reply': 'Ask me about courses, certificates, quizzes, recommendations, pricing, or your learning progress.',
            'chips': ['Recommend courses', 'Show free courses', 'How certificates work', 'Quiz help'],
            'links': [{'label': 'Browse Courses', 'url': reverse('courses:course_list')}],
        }

    if tokens.intersection({'hello', 'hi', 'hey'}):
        return {
            'reply': 'Hi, I am your Smart E-Learning AI assistant. I can help with courses, recommendations, quizzes, certificates, payments, and learning progress.',
            'chips': ['Recommend courses', 'Show free courses', 'My progress', 'What can you do'],
            'links': [{'label': 'Home', 'url': reverse('core:home')}],
        }

    if _matches_any_phrase(lower_message, ['what can you do']) or lower_message == 'help':
        return {
            'reply': (
                'I can recommend courses, explain certificate and quiz rules, answer common platform questions, '
                'show free courses, and summarize your student progress when you are logged in.'
            ),
            'chips': ['Recommend courses', 'Certificates', 'Quiz help', 'Contact support'],
            'links': [
                {'label': 'Courses', 'url': reverse('courses:course_list')},
                {'label': 'FAQ', 'url': reverse('core:faq')},
            ],
        }

    if (
        'recommend' in lower_message
        or 'suggest' in lower_message
        or _matches_any_phrase(lower_message, ['best courses', 'top courses', 'recommended courses'])
    ):
        if is_student:
            recommendations = get_personalized_recommendations(user, limit=3)
            if recommendations:
                return {
                    'reply': 'These are the strongest AI-ranked courses for your current profile.',
                    'chips': ['My progress', 'Show free courses', 'Certificates'],
                    'links': [{'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')}],
                    'cards': [
                        {
                            'title': item['course'].title,
                            'meta': f"{item['score']}% match | {item['headline']}",
                            'url': reverse('courses:course_detail', kwargs={'slug': item['course'].slug}),
                        }
                        for item in recommendations
                    ],
                }

        featured = _featured_courses()
        return {
            'reply': 'Here are some strong courses to start with. If you log in as a student, I can personalize them.',
            'chips': ['Show free courses', 'Popular categories', 'How certificates work'],
            'links': [{'label': 'Browse Courses', 'url': reverse('courses:course_list')}],
            'cards': _build_course_cards(featured),
        }

    if (
        _matches_any_phrase(lower_message, ['show free courses', 'free courses', 'free course'])
        or ('free' in lower_message and ('course' in lower_message or 'learn' in lower_message or 'show' in lower_message))
    ):
        free_courses = _free_courses()
        return {
            'reply': 'These free courses are available right now.',
            'chips': ['Recommend courses', 'Popular categories', 'Certificates'],
            'links': [{'label': 'All Courses', 'url': reverse('courses:course_list')}],
            'cards': _build_course_cards(free_courses),
        }

    if any(word in lower_message for word in ['price', 'cost', 'paid', 'fees']) or _matches_any_phrase(lower_message, ['paid courses']):
        total_free = Course.objects.filter(is_published=True, price=0).count()
        total_paid = Course.objects.filter(is_published=True).exclude(price=0).count()
        return {
            'reply': (
                f'The platform has both free and paid courses. Right now there are {total_free} free courses and {total_paid} paid courses. '
                'You can browse prices on each course page and use cart plus mock checkout for paid enrollments.'
            ),
            'chips': ['Show free courses', 'Recommend courses', 'Payment help'],
            'links': [{'label': 'Courses', 'url': reverse('courses:course_list')}],
        }

    if any(word in lower_message for word in ['certificate', 'certification']):
        if is_student:
            cert_count = Certificate.objects.filter(enrollment__student=user).count()
            extra = f' You currently have {cert_count} certificate{"s" if cert_count != 1 else ""}.'
        else:
            extra = ''
        return {
            'reply': (
                'To unlock a certificate, a student must complete the full course progress to 100% and pass at least one quiz for that course.'
                + extra
            ),
            'chips': ['Quiz help', 'My progress', 'Recommend courses'],
            'links': [{'label': 'Certificates', 'url': reverse('learning:certificates_list')}]
            if is_student
            else [{'label': 'FAQ', 'url': reverse('core:faq')}],
        }

    if 'quiz' in lower_message or 'exam' in lower_message or 'test' in lower_message:
        total_quizzes = Quiz.objects.filter(is_active=True).count()
        return {
            'reply': (
                f'The platform currently has {total_quizzes} active quizzes. Students can attempt quizzes from enrolled course pages, '
                'and passing helps with certificate eligibility.'
            ),
            'chips': ['Certificates', 'My progress', 'Recommend courses'],
            'links': [{'label': 'My Learning', 'url': reverse('learning:my_learning')}]
            if is_student
            else [{'label': 'Courses', 'url': reverse('courses:course_list')}],
        }

    if (
        'progress' in lower_message
        or 'dashboard' in lower_message
        or _matches_any_phrase(lower_message, ['my learning', 'payment history'])
    ):
        if is_student:
            return _student_progress_reply(user)
        return {
            'reply': 'Log in as a student to view your dashboard, progress analytics, wishlist, cart, and AI recommendations.',
            'chips': ['Sign in', 'Recommend courses', 'Show free courses'],
            'links': [{'label': 'Login', 'url': reverse('accounts:login')}],
        }

    if is_student and (
        'risk' in lower_message
        or 'performance' in lower_message
        or _matches_any_phrase(lower_message, ['am i at risk', 'student prediction', 'how am i performing'])
    ):
        prediction = predict_student_performance(user)
        return {
            'reply': (
                f'Your current performance prediction is {prediction["label"]} with {prediction["confidence"]}% confidence. '
                f'{prediction["explanation"]}'
            ),
            'chips': ['My progress', 'Weak topics', 'Which course should I continue'],
            'links': [{'label': 'Student Dashboard', 'url': reverse('learning:student_dashboard')}],
        }

    if is_student and (
        'weak topic' in lower_message
        or 'next lesson' in lower_message
        or 'revision' in lower_message
        or _matches_any_phrase(lower_message, ['learning path', 'what should i study now'])
    ):
        enrollment = Enrollment.objects.filter(student=user).select_related('course').order_by('-enrolled_at').first()
        if enrollment:
            path = build_learning_path(enrollment)
            next_step = path['revision_steps'][0] if path['revision_steps'] else 'Continue your next lesson.'
            weak = path['weak_lessons'][0]['title'] if path['weak_lessons'] else 'No major weak topic detected yet'
            return {
                'reply': f'Your next best step is: {next_step} Weak-topic focus: {weak}.',
                'chips': ['My progress', 'Performance prediction', 'Recommend courses'],
                'links': [{'label': 'My Learning', 'url': reverse('learning:my_learning')}],
            }

    if is_student and ('video summary' in lower_message or 'lesson highlights' in lower_message):
        enrollment = Enrollment.objects.filter(student=user).select_related('course').order_by('-enrolled_at').first()
        if enrollment:
            summary = build_video_summary(enrollment.course)
            highlights = ', '.join(item['title'] for item in summary['lesson_highlights'][:3])
            return {
                'reply': (
                    f'For {enrollment.course.title}, the main topics are {", ".join(summary["key_topics"][:4])}. '
                    f'Key lesson highlights include {highlights}.'
                ),
                'chips': ['Next lesson', 'Weak topics', 'My progress'],
                'links': [{'label': 'My Learning', 'url': reverse('learning:my_learning')}],
            }

    if 'wishlist' in lower_message or 'cart' in lower_message or 'payment' in lower_message:
        if is_student:
            wishlist_count = Wishlist.objects.filter(student=user).count()
            cart_count = CartItem.objects.filter(student=user).count()
            return {
                'reply': (
                    f'Your account currently has {wishlist_count} wishlist item{"s" if wishlist_count != 1 else ""} '
                    f'and {cart_count} cart item{"s" if cart_count != 1 else ""}.'
                ),
                'chips': ['Payment history', 'Recommend courses', 'My progress'],
                'links': [
                    {'label': 'Wishlist', 'url': reverse('learning:wishlist_page')},
                    {'label': 'Cart', 'url': reverse('learning:cart_page')},
                ],
            }
        return {
            'reply': 'Wishlist, cart, and payment history are available after student login.',
            'chips': ['Sign in', 'Recommend courses', 'Show free courses'],
            'links': [{'label': 'Login', 'url': reverse('accounts:login')}],
        }

    if 'instructor' in lower_message or 'teacher' in lower_message or _matches_any_phrase(lower_message, ['browse instructors', 'popular instructors']):
        top_instructors = (
            Course.objects.filter(is_published=True)
            .values('instructor__first_name', 'instructor__last_name', 'instructor__username')
            .annotate(total=Count('id'))
            .order_by('-total')[:3]
        )
        names = []
        for item in top_instructors:
            full_name = f"{item['instructor__first_name']} {item['instructor__last_name']}".strip()
            names.append(full_name or item['instructor__username'])
        return {
            'reply': 'Popular instructors on the platform include ' + ', '.join(names) + '.',
            'chips': ['Browse instructors', 'Recommend courses', 'Popular categories'],
            'links': [{'label': 'Instructors', 'url': reverse('core:instructor_list')}],
        }

    if (
        'category' in lower_message
        or 'categories' in lower_message
        or 'topic' in lower_message
        or _matches_any_phrase(lower_message, ['popular categories', 'top categories'])
    ):
        categories = _top_categories()
        return {
            'reply': 'These are the most popular categories on the platform right now.',
            'chips': ['Recommend courses', 'Show free courses', 'Browse courses'],
            'links': [{'label': 'Categories', 'url': reverse('courses:category_list')}],
            'cards': [
                {
                    'title': category.name,
                    'meta': f"{category.course_count} courses available",
                    'url': reverse('courses:course_list') + f'?category={category.id}',
                }
                for category in categories
            ],
        }

    if 'contact' in lower_message or 'support' in lower_message or _matches_any_phrase(lower_message, ['contact support', 'open faq']):
        return {
            'reply': 'You can reach the platform team through the contact page. If your question is common, the FAQ page may also solve it quickly.',
            'chips': ['Open FAQ', 'Courses', 'Certificates'],
            'links': [
                {'label': 'Contact', 'url': reverse('core:contact')},
                {'label': 'FAQ', 'url': reverse('core:faq')},
            ],
        }

    if _matches_any_phrase(lower_message, ['sign in', 'login', 'log in']):
        return {
            'reply': 'Use the login page to access your student dashboard, personalized recommendations, wishlist, cart, and payment history.',
            'chips': ['Recommend courses', 'Show free courses', 'What can you do'],
            'links': [{'label': 'Login', 'url': reverse('accounts:login')}],
        }

    if 'chatbot' in lower_message or 'ai' in tokens:
        return {
            'reply': (
                'This assistant uses your LMS data like courses, quizzes, categories, FAQs, and student activity to answer questions and guide learning.'
            ),
            'chips': ['Recommend courses', 'My progress', 'What can you do'],
            'links': [{'label': 'Home', 'url': reverse('core:home')}],
        }

    if is_student:
        student_learning_reply = _build_student_learning_guidance_reply(user, normalized)
        if student_learning_reply:
            return student_learning_reply

    matched_courses = _match_courses_from_message(normalized)
    if matched_courses:
        if is_student:
            personalized_course_reply = _build_student_course_query_reply(user, normalized)
            if personalized_course_reply:
                return personalized_course_reply
        return {
            'reply': 'I found these matching courses based on your question.',
            'chips': ['Recommend courses', 'Show free courses', 'Popular categories'],
            'links': [{'label': 'All Courses', 'url': reverse('courses:course_list')}],
            'cards': _build_course_cards(matched_courses),
        }

    if is_student:
        personalized_course_reply = _build_student_course_query_reply(user, normalized)
        if personalized_course_reply:
            return personalized_course_reply

    faq = _match_faq(normalized)
    if faq:
        return {
            'reply': faq.answer,
            'chips': ['Recommend courses', 'Certificates', 'Contact support'],
            'links': [{'label': 'FAQ', 'url': reverse('core:faq')}],
        }

    total_courses = Course.objects.filter(is_published=True).count()
    avg_rating = (
        Course.objects.filter(is_published=True)
        .aggregate(avg=Avg('reviews__rating', filter=Q(reviews__is_approved=True)))
        .get('avg')
        or 0
    )
    return {
        'reply': (
            f'I could not fully match that question, but I can help you explore {total_courses} courses, explain quiz and certificate rules, '
            f'and guide you around the platform. The current average approved rating is {avg_rating:.1f}.'
        ),
        'chips': ['Recommend courses', 'Show free courses', 'How certificates work', 'Contact support'],
        'links': [
            {'label': 'Courses', 'url': reverse('courses:course_list')},
            {'label': 'FAQ', 'url': reverse('core:faq')},
        ],
    }
