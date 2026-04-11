from django import forms
from .models import Customer, Loan


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['full_name', 'contact_number']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. +639123456789'
                }
            ),
        }

from django import forms
from .models import Loan

from django import forms
from .models import Loan

class LoanForm(forms.ModelForm):
    INTEREST_TYPE_CHOICES = [
        ('percent', 'Percentage (%)'),
        ('amount', 'Fixed Amount'),
    ]

    PAYMENT_FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('semi_monthly', 'Semi_monthly'),
        ('monthly', 'Monthly'),
        
    ]

    interest_type = forms.ChoiceField(
        choices=INTEREST_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Interest Type'
    )

    interest_value = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Interest'
    )

    # ✅ NEW FIELD
    payment_frequency = forms.ChoiceField(
        choices=PAYMENT_FREQUENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Payment Frequency'
    )

    payment_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Payment per Schedule'
    )

    class Meta:
        model = Loan
        fields = [
            'loan_amount',
            'interest_type',
            'interest_value',
            'payment_frequency',
            'payment_amount',  # ✅ NEW
            'start_date',
            'due_date'
        ]
        widgets = {
            'loan_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


    def clean(self):
        cleaned_data = super().clean()
        payment_amount = cleaned_data.get('payment_amount')
        due_date = cleaned_data.get('due_date')

        # detect auto mode (payment_amount exists)
        if payment_amount and payment_amount > 0:
            # auto mode → due date NOT required
            return cleaned_data

        # manual mode → due date required
        if not due_date:
            raise forms.ValidationError("Due Date is required when Payment Amount is not set.")

        return cleaned_data

from django import forms
from .models import EmergencyLoan, EmergencyPaymentSchedule  # or EmergencyLoan if you have a separate model


class EmergencyLoanForm(forms.ModelForm):
    class Meta:
        model = EmergencyLoan  # change to EmergencyLoan if that's your model
        fields = [
            'loan_amount',
            'interest_percent',
            'schedule_day',
            'start_date'
        ]

        widgets = {
            'loan_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter loan amount'
            }),
            'interest_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter interest %'
            }),
            'schedule_day': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    # Optional validation
    def clean_interest_percent(self):
        interest = self.cleaned_data.get('interest_percent')
        if interest < 0:
            raise forms.ValidationError("Interest cannot be negative.")
        return interest

    def clean_loan_amount(self):
        amount = self.cleaned_data.get('loan_amount')
        if amount <= 0:
            raise forms.ValidationError("Loan amount must be greater than 0.")
        return amount

class PrincipalPaymentForm(forms.ModelForm):
    class Meta:
        model = EmergencyPaymentSchedule
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter principal payment'}),
        }

from django import forms
from .models import PaymentSchedule

class PaymentForm(forms.ModelForm):
    class Meta:
        model = PaymentSchedule
        fields = ['paid_amount']