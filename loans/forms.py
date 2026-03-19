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

    interest_type = forms.ChoiceField(
        choices=INTEREST_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Interest Type'
    )
    interest_value = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Interest'
    )

    class Meta:
        model = Loan
        fields = ['loan_amount', 'interest_type', 'interest_value', 'start_date', 'due_date']
        widgets = {
            'loan_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }