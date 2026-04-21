from django import forms
from django.core.exceptions import ValidationError

from .models import AssignmentSubmission, EngagementSnapshot, Enrollment


class PaymentMethodForm(forms.Form):
    MOCK_SUCCESS = 'success'
    MOCK_FAILED = 'failed'
    MOCK_PENDING = 'pending'
    MOCK_RANDOM = 'random'
    MOCK_RESULT_CHOICES = (
        (MOCK_SUCCESS, 'Always Success'),
        (MOCK_FAILED, 'Always Failed'),
        (MOCK_PENDING, 'Pending'),
        (MOCK_RANDOM, 'Random Success/Failure'),
    )

    payment_method = forms.ChoiceField(
        choices=Enrollment.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        label='Select Payment Method',
    )
    upi_id = forms.CharField(required=False, max_length=100, label='UPI ID', help_text='Example: name@upi')

    card_holder_name = forms.CharField(required=False, max_length=120, label='Card Holder Name')
    card_number = forms.CharField(required=False, max_length=19, label='Card Number')
    card_expiry = forms.CharField(required=False, max_length=5, label='Expiry (MM/YY)')
    card_cvv = forms.CharField(required=False, max_length=4, label='CVV')

    bank_name = forms.CharField(required=False, max_length=120, label='Bank Name')
    netbanking_user_id = forms.CharField(required=False, max_length=120, label='Net Banking User ID')
    mock_result = forms.ChoiceField(
        choices=MOCK_RESULT_CHOICES,
        required=False,
        initial=MOCK_SUCCESS,
        label='Mock Payment Result (Demo)',
    )

    agree_terms = forms.BooleanField(required=True, label='I agree to the payment and refund policy.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['upi_id'].widget.attrs.update({'placeholder': 'example@upi'})
        self.fields['card_holder_name'].widget.attrs.update({'placeholder': 'Name on card'})
        self.fields['card_number'].widget.attrs.update({'placeholder': '16-digit card number', 'inputmode': 'numeric'})
        self.fields['card_expiry'].widget.attrs.update({'placeholder': 'MM/YY', 'inputmode': 'numeric'})
        self.fields['card_cvv'].widget.attrs.update({'placeholder': 'CVV', 'inputmode': 'numeric', 'type': 'password'})
        self.fields['bank_name'].widget.attrs.update({'placeholder': 'Your bank name'})
        self.fields['netbanking_user_id'].widget.attrs.update({'placeholder': 'Net banking user ID'})
        self.fields['mock_result'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')

        if payment_method == Enrollment.PAYMENT_UPI:
            upi_id = (cleaned_data.get('upi_id') or '').strip()
            if not upi_id:
                self.add_error('upi_id', 'UPI ID is required for UPI payments.')
            elif '@' not in upi_id:
                self.add_error('upi_id', 'Enter a valid UPI ID (example@upi).')

        elif payment_method == Enrollment.PAYMENT_CARD:
            card_holder_name = (cleaned_data.get('card_holder_name') or '').strip()
            card_number = (cleaned_data.get('card_number') or '').replace(' ', '')
            card_expiry = (cleaned_data.get('card_expiry') or '').strip()
            card_cvv = (cleaned_data.get('card_cvv') or '').strip()

            if not card_holder_name:
                self.add_error('card_holder_name', 'Card holder name is required.')
            if not card_number or not card_number.isdigit() or len(card_number) not in {16}:
                self.add_error('card_number', 'Enter a valid 16-digit card number.')
            if len(card_expiry) != 5 or card_expiry[2] != '/':
                self.add_error('card_expiry', 'Enter expiry in MM/YY format.')
            else:
                month = card_expiry[:2]
                year = card_expiry[3:]
                if not month.isdigit() or not year.isdigit() or not (1 <= int(month) <= 12):
                    self.add_error('card_expiry', 'Enter a valid expiry month.')
            if not card_cvv.isdigit() or len(card_cvv) not in {3, 4}:
                self.add_error('card_cvv', 'Enter a valid CVV.')

        elif payment_method == Enrollment.PAYMENT_NET_BANKING:
            bank_name = (cleaned_data.get('bank_name') or '').strip()
            netbanking_user_id = (cleaned_data.get('netbanking_user_id') or '').strip()
            if not bank_name:
                self.add_error('bank_name', 'Bank name is required for net banking.')
            if not netbanking_user_id:
                self.add_error('netbanking_user_id', 'Net banking user ID is required.')

        elif payment_method == Enrollment.PAYMENT_WALLET:
            # Wallet does not require extra details in this demo flow.
            pass
        else:
            raise ValidationError('Please select a valid payment method.')

        if cleaned_data.get('mock_result') not in dict(self.MOCK_RESULT_CHOICES):
            cleaned_data['mock_result'] = self.MOCK_SUCCESS

        return cleaned_data


class EngagementSnapshotForm(forms.ModelForm):
    class Meta:
        model = EngagementSnapshot
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['title', 'content']
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Paste assignment or answer text to check similarity against existing submissions.',
                }
            ),
        }
