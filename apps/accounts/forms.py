from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import InstructorProfile, StudentProfile, User


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username or Email',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Email'}),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


class StudentRegistrationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text='Use letters/numbers with @ . + - _. Spaces will be converted to _.',
    )
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email is already registered.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        username = '_'.join(username.split())

        username_validator = UnicodeUsernameValidator()
        try:
            username_validator(username)
        except forms.ValidationError:
            raise forms.ValidationError('Enter a valid username. Example: rahul_verma')

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')

        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower()
        user.role = User.STUDENT
        if commit:
            user.save()
        return user


class InstructorRegistrationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text='Use letters/numbers with @ . + - _. Spaces will be converted to _.',
    )
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    headline = forms.CharField(max_length=180, required=False)
    qualification = forms.CharField(max_length=120, required=False)
    experience_years = forms.IntegerField(min_value=0, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email is already registered.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        username = '_'.join(username.split())

        username_validator = UnicodeUsernameValidator()
        try:
            username_validator(username)
        except forms.ValidationError:
            raise forms.ValidationError('Enter a valid username. Example: rahul_verma')

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')

        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower()
        user.role = User.INSTRUCTOR
        if commit:
            user.save()
            profile = user.instructor_profile
            profile.headline = self.cleaned_data.get('headline', '')
            profile.qualification = self.cleaned_data.get('qualification', '')
            profile.experience_years = self.cleaned_data.get('experience_years') or 0
            profile.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'avatar', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['enrollment_no', 'university', 'semester', 'city', 'learning_interests']
        widgets = {
            'learning_interests': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Example: Python, machine learning, cybersecurity',
                }
            ),
        }


class InstructorProfileForm(forms.ModelForm):
    class Meta:
        model = InstructorProfile
        fields = ['headline', 'qualification', 'experience_years', 'expertise']


class UserPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
