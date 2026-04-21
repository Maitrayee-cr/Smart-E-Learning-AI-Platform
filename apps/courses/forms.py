from django import forms

from .models import Category, Course, CourseSection, Lesson, LessonResource, Quiz, Question, Review


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'icon', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class CourseFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    level = forms.ChoiceField(
        required=False,
        choices=(('', 'All Levels'),) + Course.LEVEL_CHOICES,
    )
    pricing = forms.ChoiceField(
        required=False,
        choices=(
            ('', 'All'),
            ('free', 'Free'),
            ('paid', 'Paid'),
        ),
    )
    sort = forms.ChoiceField(
        required=False,
        choices=(
            ('latest', 'Latest'),
            ('rating', 'Top Rated'),
            ('price_asc', 'Price: Low to High'),
            ('price_desc', 'Price: High to Low'),
        ),
        initial='latest',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = (
            Category.objects.filter(is_active=True)
            .exclude(name__iexact='School Courses')
            .exclude(name__iexact='Commerce')
            .exclude(name__iexact='Aptitude')
        )


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'category',
            'title',
            'short_description',
            'description',
            'thumbnail',
            'full_course_video',
            'background_image',
            'level',
            'duration_hours',
            'language',
            'price',
            'is_featured',
            'is_published',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'thumbnail': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'full_course_video': forms.ClearableFileInput(attrs={'accept': 'video/*'}),
            'background_image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_thumbnail(self):
        return self._validate_image('thumbnail', 3)

    def clean_background_image(self):
        return self._validate_image('background_image', 5)

    def clean_full_course_video(self):
        video_file = self.cleaned_data.get('full_course_video')
        if not video_file or not hasattr(video_file, 'content_type'):
            return video_file

        allowed_types = {
            'video/mp4',
            'video/webm',
            'video/quicktime',
            'video/x-msvideo',
            'video/mpeg',
        }
        if video_file.content_type not in allowed_types:
            raise forms.ValidationError('Please upload MP4, WEBM, MOV, AVI, or MPEG video.')

        if video_file.size > 200 * 1024 * 1024:
            raise forms.ValidationError('Video size must be less than 200 MB.')

        return video_file

    def _validate_image(self, field_name, max_size_mb):
        image_file = self.cleaned_data.get(field_name)
        if not image_file:
            return image_file

        if not hasattr(image_file, 'content_type'):
            return image_file

        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        if image_file.content_type not in allowed_types:
            raise forms.ValidationError('Please upload a JPG, PNG, or WEBP image.')

        if image_file.size > max_size_mb * 1024 * 1024:
            raise forms.ValidationError(f'Image size must be less than {max_size_mb} MB.')

        return image_file


class CourseSectionForm(forms.ModelForm):
    class Meta:
        model = CourseSection
        fields = ['title', 'description', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'description', 'video_file', 'duration_minutes', 'order', 'is_preview', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class LessonResourceForm(forms.ModelForm):
    class Meta:
        model = LessonResource
        fields = ['title', 'resource_type', 'file', 'external_url']


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'pass_percentage', 'time_limit_minutes', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class QuestionForm(forms.ModelForm):
    option_1 = forms.CharField(max_length=250)
    option_2 = forms.CharField(max_length=250)
    option_3 = forms.CharField(max_length=250)
    option_4 = forms.CharField(max_length=250)
    correct_option = forms.ChoiceField(choices=(('1', 'Option 1'), ('2', 'Option 2'), ('3', 'Option 3'), ('4', 'Option 4')))

    class Meta:
        model = Question
        fields = ['text', 'order', 'marks', 'difficulty']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2}),
        }


class AIQuizGeneratorForm(forms.Form):
    question_count = forms.IntegerField(min_value=3, max_value=10, initial=5)
    difficulty = forms.ChoiceField(choices=Question.DIFFICULTY_CHOICES, initial=Question.MEDIUM)
    source_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 4,
                'placeholder': 'Paste extra notes or uploaded content text to generate smarter MCQs.',
            }
        ),
    )


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
