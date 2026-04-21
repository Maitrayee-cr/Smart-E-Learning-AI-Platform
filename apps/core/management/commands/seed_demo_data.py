from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import FAQ, ContactMessage, Testimonial
from apps.courses.models import Category, Course, CourseSection, Lesson, Option, Question, Quiz, Review
from apps.learning.models import Enrollment


class Command(BaseCommand):
    help = 'Seed realistic demo data for Smart E-Learning Management System.'

    def handle(self, *args, **options):
        User = get_user_model()

        categories_data = [
            'Programming',
            'Web Development',
            'DBMS',
            'Data Science',
            'Machine Learning',
            'Artificial Intelligence',
            'Cyber Security',
            'Aptitude & Reasoning',
        ]

        category_map = {}
        for name in categories_data:
            category, _ = Category.objects.get_or_create(name=name, defaults={'description': f'{name} courses'})
            category_map[name] = category

        instructors_seed = [
            ('anita_shah', 'Anita', 'Shah', 'Python Mentor', 'M.Tech Computer Engineering', 7, 'Python, OOP, Problem Solving'),
            ('rohan_patel', 'Rohan', 'Patel', 'Full Stack Expert', 'B.E. Information Technology', 6, 'Django, React, APIs'),
            ('meera_joshi', 'Meera', 'Joshi', 'Data Science Coach', 'M.Sc Data Analytics', 8, 'Data Science, ML, Statistics'),
            ('rahul_verma', 'Rahul', 'Verma', 'Cyber Security Specialist', 'B.Tech Cyber Security', 5, 'Cyber Security, Ethical Hacking, Network Security'),
            ('priya_mehta', 'Priya', 'Mehta', 'Aptitude & Reasoning Trainer', 'M.Sc Mathematics', 6, 'Aptitude, Logical Reasoning, Quantitative Skills'),
        ]

        instructor_users = []
        instructor_map = {}
        for username, first, last, headline, qualification, exp, expertise in instructors_seed:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@smartlms.com',
                    'role': User.INSTRUCTOR,
                },
            )
            if created:
                user.set_password('Pass@123')
                user.save()
            user.role = User.INSTRUCTOR
            user.save(update_fields=['role'])
            if hasattr(user, 'instructor_profile'):
                profile = user.instructor_profile
                profile.headline = headline
                profile.qualification = qualification
                profile.experience_years = exp
                profile.expertise = expertise
                profile.approved = True
                profile.save()
            instructor_users.append(user)
            instructor_map[username] = user

        students_seed = [
            ('aisha', 'Aisha', 'Khan', 'aisha@gmail.com', '12345'),
            ('rahul', 'Rahul', 'Sharma', 'rahul@gmail.com', '12345'),
            ('sneha', 'Sneha', 'Patel', 'sneha@gmail.com', '12345'),
            ('arjun', 'Arjun', 'Mehta', 'arjun@gmail.com', '12345'),
            ('priya', 'Priya', 'Singh', 'priya@gmail.com', '12345'),
            ('karan', 'Karan', 'Verma', 'karan@gmail.com', '12345'),
            ('neha', 'Neha', 'Gupta', 'neha@gmail.com', '12345'),
            ('rohan_student', 'Rohan', 'Desai', 'rohan@gmail.com', '12345'),
        ]

        student_users = []
        for idx, (username, first, last, email, password) in enumerate(students_seed, start=1):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': email,
                    'role': User.STUDENT,
                },
            )

            # Keep student credentials aligned with requested demo accounts.
            user.first_name = first
            user.last_name = last
            user.email = email
            user.role = User.STUDENT
            user.set_password(password)
            user.save()

            if hasattr(user, 'student_profile'):
                sp = user.student_profile
                sp.university = 'GTU'
                sp.semester = 8
                sp.city = 'Ahmedabad'
                sp.enrollment_no = f'GTU2026{idx:03d}'
                sp.save()
            student_users.append(user)

        admin_user, created = User.objects.get_or_create(
            username='platformadmin',
            defaults={
                'first_name': 'Platform',
                'last_name': 'Admin',
                'email': 'admin@smartlms.com',
                'role': User.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin_user.set_password('Admin@123')
            admin_user.save()

        courses_seed = [
            {
                'title': 'Python for Beginners',
                'instructor': 'anita_shah',
                'category': 'Programming',
                'slug': 'python-for-beginners',
                'short_description': 'Learn Python basics with simple examples.',
                'description': 'This course introduces Python programming including variables, loops, and functions.',
                'price': Decimal('0.00'),
                'level': Course.BEGINNER,
                'duration_hours': 24,
            },
            {
                'title': 'Java Programming',
                'instructor': 'anita_shah',
                'category': 'Programming',
                'slug': 'java-programming',
                'short_description': 'Learn Java from scratch.',
                'description': 'Covers Java fundamentals, OOP concepts, and basic applications.',
                'price': Decimal('899.00'),
                'level': Course.BEGINNER,
                'duration_hours': 30,
            },
            {
                'title': 'Data Structures in C++',
                'instructor': 'anita_shah',
                'category': 'Programming',
                'slug': 'data-structures-cpp',
                'short_description': 'Learn core data structures.',
                'description': 'Includes arrays, linked lists, stacks, and queues with examples.',
                'price': Decimal('999.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 34,
            },
            {
                'title': 'HTML CSS JavaScript Masterclass',
                'instructor': 'rohan_patel',
                'category': 'Web Development',
                'slug': 'html-css-js-masterclass',
                'short_description': 'Build responsive websites.',
                'description': 'Learn frontend development using HTML, CSS, and JavaScript.',
                'price': Decimal('1299.00'),
                'level': Course.BEGINNER,
                'duration_hours': 36,
            },
            {
                'title': 'Full Stack Web Development',
                'instructor': 'rohan_patel',
                'category': 'Web Development',
                'slug': 'full-stack-web-development',
                'short_description': 'Build complete web apps.',
                'description': 'Covers frontend and backend using Django and databases.',
                'price': Decimal('1999.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 48,
            },
            {
                'title': 'Django Web Development',
                'instructor': 'rohan_patel',
                'category': 'Web Development',
                'slug': 'django-web-development',
                'short_description': 'Learn backend with Django.',
                'description': 'Build scalable web applications using Django framework.',
                'price': Decimal('1499.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 40,
            },
            {
                'title': 'DBMS Basics',
                'instructor': 'rohan_patel',
                'category': 'DBMS',
                'slug': 'dbms-basics',
                'short_description': 'Learn database fundamentals.',
                'description': 'Covers ER models, normalization, and database design.',
                'price': Decimal('599.00'),
                'level': Course.BEGINNER,
                'duration_hours': 26,
            },
            {
                'title': 'SQL for Students',
                'instructor': 'meera_joshi',
                'category': 'DBMS',
                'slug': 'sql-for-students',
                'short_description': 'Learn SQL basics.',
                'description': 'Includes queries, joins, and database operations.',
                'price': Decimal('0.00'),
                'level': Course.BEGINNER,
                'duration_hours': 22,
            },
            {
                'title': 'Data Science Basics',
                'instructor': 'meera_joshi',
                'category': 'Data Science',
                'slug': 'data-science-basics',
                'short_description': 'Introduction to data science.',
                'description': 'Covers data analysis, statistics, and visualization.',
                'price': Decimal('1199.00'),
                'level': Course.BEGINNER,
                'duration_hours': 32,
            },
            {
                'title': 'Data Analysis with Python',
                'instructor': 'meera_joshi',
                'category': 'Data Science',
                'slug': 'data-analysis-python',
                'short_description': 'Analyze data using Python.',
                'description': 'Learn pandas, numpy, and data handling techniques.',
                'price': Decimal('1399.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 36,
            },
            {
                'title': 'Machine Learning Essentials',
                'instructor': 'meera_joshi',
                'category': 'Machine Learning',
                'slug': 'machine-learning-essentials',
                'short_description': 'Learn ML basics.',
                'description': 'Covers supervised and unsupervised learning.',
                'price': Decimal('1499.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 38,
            },
            {
                'title': 'Supervised Learning Techniques',
                'instructor': 'meera_joshi',
                'category': 'Machine Learning',
                'slug': 'supervised-learning',
                'short_description': 'Learn supervised ML.',
                'description': 'Includes regression and classification models.',
                'price': Decimal('1299.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 34,
            },
            {
                'title': 'AI Fundamentals',
                'instructor': 'meera_joshi',
                'category': 'Artificial Intelligence',
                'slug': 'ai-fundamentals',
                'short_description': 'Introduction to AI.',
                'description': 'Covers intelligent systems and AI concepts.',
                'price': Decimal('1499.00'),
                'level': Course.BEGINNER,
                'duration_hours': 32,
            },
            {
                'title': 'Deep Learning Introduction',
                'instructor': 'meera_joshi',
                'category': 'Artificial Intelligence',
                'slug': 'deep-learning-intro',
                'short_description': 'Learn deep learning basics.',
                'description': 'Covers neural networks and deep learning models.',
                'price': Decimal('1599.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 40,
            },
            {
                'title': 'Cyber Security Fundamentals',
                'instructor': 'rahul_verma',
                'category': 'Cyber Security',
                'slug': 'cyber-security-fundamentals',
                'short_description': 'Learn security basics.',
                'description': 'Covers threats, attacks, and protection techniques.',
                'price': Decimal('999.00'),
                'level': Course.BEGINNER,
                'duration_hours': 30,
            },
            {
                'title': 'Ethical Hacking Basics',
                'instructor': 'rahul_verma',
                'category': 'Cyber Security',
                'slug': 'ethical-hacking-basics',
                'short_description': 'Learn ethical hacking.',
                'description': 'Introduction to hacking tools and techniques.',
                'price': Decimal('1299.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 34,
            },
            {
                'title': 'Network Security',
                'instructor': 'rahul_verma',
                'category': 'Cyber Security',
                'slug': 'network-security',
                'short_description': 'Learn network protection.',
                'description': 'Covers firewalls, protocols, and network safety.',
                'price': Decimal('1199.00'),
                'level': Course.INTERMEDIATE,
                'duration_hours': 32,
            },
            {
                'title': 'Quantitative Aptitude Mastery',
                'instructor': 'priya_mehta',
                'category': 'Aptitude & Reasoning',
                'slug': 'quantitative-aptitude',
                'short_description': 'Improve aptitude skills.',
                'description': 'Covers percentages, ratios, and problem solving.',
                'price': Decimal('499.00'),
                'level': Course.BEGINNER,
                'duration_hours': 24,
            },
            {
                'title': 'Logical Reasoning Basics',
                'instructor': 'priya_mehta',
                'category': 'Aptitude & Reasoning',
                'slug': 'logical-reasoning',
                'short_description': 'Learn reasoning skills.',
                'description': 'Covers puzzles, patterns, and logical thinking.',
                'price': Decimal('499.00'),
                'level': Course.BEGINNER,
                'duration_hours': 24,
            },
            {
                'title': 'Verbal Ability',
                'instructor': 'priya_mehta',
                'category': 'Aptitude & Reasoning',
                'slug': 'verbal-ability',
                'short_description': 'Improve English skills.',
                'description': 'Covers grammar, vocabulary, and comprehension.',
                'price': Decimal('499.00'),
                'level': Course.BEGINNER,
                'duration_hours': 24,
            },
        ]

        quiz_question_bank = {
            'Programming': [
                {
                    'text': 'Which keyword is used to define a function in Python?',
                    'options': ['func', 'def', 'function', 'lambda'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which data structure follows LIFO order?',
                    'options': ['Queue', 'Array', 'Stack', 'Linked List'],
                    'correct_index': 2,
                },
                {
                    'text': 'In OOP, what does inheritance help with?',
                    'options': ['Data encryption', 'Code reusability', 'Memory cleanup only', 'Faster internet'],
                    'correct_index': 1,
                },
                {
                    'text': 'What is the output type of 5 / 2 in Python 3?',
                    'options': ['int', 'float', 'str', 'bool'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which C++ container allows dynamic resizing?',
                    'options': ['int[]', 'vector', 'tuple', 'stack frame'],
                    'correct_index': 1,
                },
            ],
            'Web Development': [
                {
                    'text': 'Which HTML tag is used to create a hyperlink?',
                    'options': ['<link>', '<a>', '<href>', '<url>'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which CSS property controls text size?',
                    'options': ['font-style', 'text-size', 'font-size', 'text-weight'],
                    'correct_index': 2,
                },
                {
                    'text': 'Which method is commonly used for creating data on a server?',
                    'options': ['GET', 'POST', 'DELETE', 'HEAD'],
                    'correct_index': 1,
                },
                {
                    'text': 'In Django, which file typically defines URL routes for an app?',
                    'options': ['models.py', 'views.py', 'urls.py', 'admin.py'],
                    'correct_index': 2,
                },
                {
                    'text': 'JavaScript runs primarily on which side for frontend logic?',
                    'options': ['Database side', 'Client side', 'Compiler side', 'Kernel side'],
                    'correct_index': 1,
                },
            ],
            'DBMS': [
                {
                    'text': 'Which SQL command is used to retrieve data?',
                    'options': ['GET', 'SELECT', 'FETCH ALL', 'PULL'],
                    'correct_index': 1,
                },
                {
                    'text': 'What does normalization primarily reduce?',
                    'options': ['Data redundancy', 'Network speed', 'UI lag', 'CPU temperature'],
                    'correct_index': 0,
                },
                {
                    'text': 'Which key uniquely identifies each row in a table?',
                    'options': ['Foreign Key', 'Alternate Key', 'Primary Key', 'Composite Value'],
                    'correct_index': 2,
                },
                {
                    'text': 'Which SQL clause is used to filter rows?',
                    'options': ['GROUP BY', 'WHERE', 'ORDER BY', 'HAVING'],
                    'correct_index': 1,
                },
                {
                    'text': 'A relationship between two tables is usually established using:',
                    'options': ['Primary-Primary Pair', 'Foreign Key', 'Unique Index only', 'Trigger'],
                    'correct_index': 1,
                },
            ],
            'Data Science': [
                {
                    'text': 'Which Python library is widely used for tabular data analysis?',
                    'options': ['NumPy', 'Pandas', 'Matplotlib', 'Seaborn'],
                    'correct_index': 1,
                },
                {
                    'text': 'Mean, median, and mode are examples of:',
                    'options': ['Visualization tools', 'Central tendency measures', 'Neural networks', 'Clustering algorithms'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which library is commonly used for numerical operations in Python?',
                    'options': ['Django', 'Flask', 'NumPy', 'BeautifulSoup'],
                    'correct_index': 2,
                },
                {
                    'text': 'A chart used to show distribution of values is:',
                    'options': ['Histogram', 'Flowchart', 'Class diagram', 'Tree map only'],
                    'correct_index': 0,
                },
                {
                    'text': 'Data cleaning typically happens:',
                    'options': ['Before analysis', 'After deployment only', 'Never needed', 'Only in production'],
                    'correct_index': 0,
                },
            ],
            'Machine Learning': [
                {
                    'text': 'Supervised learning requires:',
                    'options': ['Unlabeled data only', 'Labeled training data', 'No data', 'Only text data'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which is a common classification algorithm?',
                    'options': ['Linear Regression', 'Logistic Regression', 'K-Means', 'Apriori'],
                    'correct_index': 1,
                },
                {
                    'text': 'Overfitting means the model:',
                    'options': ['Performs well on new data', 'Memorizes training data too much', 'Uses too little data always', 'Cannot be trained'],
                    'correct_index': 1,
                },
                {
                    'text': 'Which metric is widely used for classification accuracy evaluation?',
                    'options': ['RMSE only', 'Accuracy score', 'Silhouette score only', 'AIC only'],
                    'correct_index': 1,
                },
                {
                    'text': 'Unsupervised learning example:',
                    'options': ['Spam detection', 'Image classification', 'K-Means clustering', 'Price prediction'],
                    'correct_index': 2,
                },
            ],
            'Artificial Intelligence': [
                {
                    'text': 'AI is primarily about creating systems that can:',
                    'options': ['Only store files', 'Mimic intelligent behavior', 'Increase monitor brightness', 'Replace electricity'],
                    'correct_index': 1,
                },
                {
                    'text': 'Deep learning models are based on:',
                    'options': ['Binary trees', 'Neural networks', 'Linked lists', 'Hash maps'],
                    'correct_index': 1,
                },
                {
                    'text': 'Natural Language Processing deals with:',
                    'options': ['Audio cables', 'Human language text/speech', 'Only images', 'Network hardware'],
                    'correct_index': 1,
                },
                {
                    'text': 'A key application of AI is:',
                    'options': ['Chatbots', 'Power sockets', 'USB formatting only', 'Compiler removal'],
                    'correct_index': 0,
                },
                {
                    'text': 'Which framework is popular for deep learning?',
                    'options': ['TensorFlow', 'Bootstrap', 'SQLite', 'Pillow only'],
                    'correct_index': 0,
                },
            ],
            'Cyber Security': [
                {
                    'text': 'Phishing is a type of:',
                    'options': ['Database indexing', 'Social engineering attack', 'CPU optimization', 'Data visualization'],
                    'correct_index': 1,
                },
                {
                    'text': 'A firewall is mainly used to:',
                    'options': ['Block/allow network traffic', 'Create UI pages', 'Compile Python', 'Encrypt monitors'],
                    'correct_index': 0,
                },
                {
                    'text': 'Strong password practice includes:',
                    'options': ['Using only name', 'Using 123456', 'Using mixed characters and symbols', 'Reusing one password everywhere'],
                    'correct_index': 2,
                },
                {
                    'text': 'Ethical hacking is performed to:',
                    'options': ['Exploit without permission', 'Improve system security legally', 'Delete backups', 'Increase piracy'],
                    'correct_index': 1,
                },
                {
                    'text': 'HTTPS helps by providing:',
                    'options': ['Unencrypted transfer', 'Encrypted communication', 'Faster typing speed', 'Automatic backups only'],
                    'correct_index': 1,
                },
            ],
            'Aptitude & Reasoning': [
                {
                    'text': 'If 20% of a number is 40, the number is:',
                    'options': ['100', '150', '200', '250'],
                    'correct_index': 2,
                },
                {
                    'text': 'Find the odd one out: 2, 3, 5, 9, 11',
                    'options': ['2', '3', '5', '9'],
                    'correct_index': 3,
                },
                {
                    'text': 'A train covers 60 km in 1 hour. Its speed is:',
                    'options': ['30 km/h', '60 km/h', '90 km/h', '120 km/h'],
                    'correct_index': 1,
                },
                {
                    'text': 'Choose the correct analogy: Book : Read :: Food : ?',
                    'options': ['Cook', 'Eat', 'Serve', 'Buy'],
                    'correct_index': 1,
                },
                {
                    'text': 'If ALL CATS are ANIMALS and some ANIMALS are PETS, then:',
                    'options': ['All pets are cats', 'Some cats may be pets', 'No cats are animals', 'All animals are cats'],
                    'correct_index': 1,
                },
            ],
        }

        for idx, course_data in enumerate(courses_seed, start=1):
            title = course_data['title']
            category_name = course_data['category']
            instructor = instructor_map[course_data['instructor']]
            course, _ = Course.objects.update_or_create(
                title=title,
                defaults={
                    'instructor': instructor,
                    'category': category_map[category_name],
                    'slug': course_data['slug'],
                    'short_description': course_data['short_description'],
                    'description': course_data['description'],
                    'level': course_data['level'],
                    'duration_hours': course_data['duration_hours'],
                    'language': 'English',
                    'price': course_data['price'],
                    'is_featured': idx <= 8,
                    'is_published': True,
                },
            )

            quiz_questions = quiz_question_bank.get(category_name, quiz_question_bank['Programming'])
            quiz_section, _ = CourseSection.objects.get_or_create(
                course=course,
                title='Final Assessment',
                defaults={
                    'description': 'Auto-generated internal section for course quiz.',
                    'order': 999,
                },
            )
            quiz_lesson, _ = Lesson.objects.get_or_create(
                section=quiz_section,
                title='Course Final Quiz Lesson',
                defaults={
                    'description': 'Auto-generated lesson used for final assessment.',
                    'duration_minutes': 20,
                    'order': 1,
                    'is_preview': False,
                    'notes': 'Attempt the final quiz to test your course understanding.',
                },
            )
            quiz, _ = Quiz.objects.get_or_create(
                lesson=quiz_lesson,
                title='Course Final Quiz',
                defaults={
                    'description': f'Auto-generated final quiz for {course.title}.',
                    'pass_percentage': 40,
                    'time_limit_minutes': 20,
                    'is_active': True,
                },
            )
            quiz.description = f'Auto-generated final quiz for {course.title}.'
            quiz.pass_percentage = 40
            quiz.time_limit_minutes = 20
            quiz.is_active = True
            quiz.save(update_fields=['description', 'pass_percentage', 'time_limit_minutes', 'is_active', 'updated_at'])

            quiz.questions.all().delete()
            for q_index, item in enumerate(quiz_questions, start=1):
                question = Question.objects.create(
                    quiz=quiz,
                    text=item['text'],
                    order=q_index,
                    marks=1,
                )
                for option_index, option_text in enumerate(item['options']):
                    Option.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=option_index == item['correct_index'],
                    )

        # Remove old auto-generated generic modules from any course.
        generic_section_titles = ['Module 1', 'Module 2', 'Module 3']
        deleted_sections_count, _ = CourseSection.objects.filter(
            title__in=generic_section_titles,
            description__startswith='Core concepts for module',
        ).delete()
        if deleted_sections_count:
            self.stdout.write(
                self.style.WARNING(
                    f'Removed {deleted_sections_count} generic section record(s) (Module 1/2/3).'
                )
            )

        for student in student_users:
            for course in Course.objects.filter(is_published=True)[:4]:
                defaults = {
                    'payment_status': Enrollment.PAYMENT_FREE,
                    'paid_amount': Decimal('0.00'),
                }
                if course.price > 0:
                    defaults.update(
                        {
                            'payment_status': Enrollment.PAYMENT_PAID,
                            'payment_method': Enrollment.PAYMENT_UPI,
                            'paid_amount': course.price,
                            'payment_reference': f'SEED-{student.id}-{course.id}',
                            'payment_at': timezone.now(),
                        }
                    )

                enrollment, created = Enrollment.objects.get_or_create(
                    student=student,
                    course=course,
                    defaults=defaults,
                )
                if not created and course.price > 0 and enrollment.payment_status != Enrollment.PAYMENT_PAID:
                    enrollment.payment_status = Enrollment.PAYMENT_PAID
                    enrollment.payment_method = Enrollment.PAYMENT_UPI
                    enrollment.paid_amount = course.price
                    enrollment.payment_reference = enrollment.payment_reference or f'SEED-{student.id}-{course.id}'
                    enrollment.payment_at = enrollment.payment_at or timezone.now()
                    enrollment.save(
                        update_fields=[
                            'payment_status',
                            'payment_method',
                            'paid_amount',
                            'payment_reference',
                            'payment_at',
                            'updated_at',
                        ]
                    )

        for course in Course.objects.all()[:6]:
            for student in student_users[:3]:
                Review.objects.get_or_create(
                    course=course,
                    student=student,
                    defaults={'rating': 4, 'comment': 'Very helpful and well-structured course.'},
                )

        FAQ.objects.get_or_create(
            question='How do I enroll in a course?',
            defaults={'answer': 'Open a course detail page and click Enroll Now.', 'order': 1},
        )
        FAQ.objects.get_or_create(
            question='When will I get my certificate?',
            defaults={'answer': 'You receive it automatically after passing the course quiz.', 'order': 2},
        )

        Testimonial.objects.get_or_create(
            name='Harshil Trivedi',
            defaults={
                'designation': 'B.E Student',
                'content': 'The platform made my exam preparation very organized and efficient.',
                'rating': 5,
            },
        )
        Testimonial.objects.get_or_create(
            name='Neha Mehta',
            defaults={
                'designation': 'MCA Aspirant',
                'content': 'Great UI and clear modules improved my confidence.',
                'rating': 5,
            },
        )

        ContactMessage.objects.get_or_create(
            email='demo@student.com',
            subject='Demo support request',
            defaults={
                'name': 'Demo User',
                'phone': '9999999999',
                'message': 'Need help with certificate download.',
            },
        )

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
