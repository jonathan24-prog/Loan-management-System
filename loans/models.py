from django.db import models

from django.db import models

class Customer(models.Model):
    full_name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=20, blank=True, null=True)

    @property
    def is_active(self):
        return self.loans.filter(remaining_balance__gt=0).exists()

    def __str__(self):
        return self.full_name

        # models.py
from django.db import models
from decimal import Decimal

# models.py
from django.db import models

from django.db import models

class Loan(models.Model):
    INTEREST_TYPE_CHOICES = [
        ('percent', 'Percentage (%)'),
        ('amount', 'Fixed Amount'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_type = models.CharField(max_length=10, choices=INTEREST_TYPE_CHOICES, default='percent')
    interest_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # either percent or fixed
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Total loan+interest
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # gets reduced on payment
    start_date = models.DateField()
    due_date = models.DateField()

    def save(self, *args, **kwargs):
        # Only calculate balance if creating a new loan
        if not self.pk:
            if self.interest_type == 'percent':
                self.balance = self.loan_amount + (self.loan_amount * self.interest_value / 100)
            else:
                self.balance = self.loan_amount + self.interest_value
            self.remaining_balance = self.balance  # initialize remaining balance
        super().save(*args, **kwargs)

    @property
    def total_paid(self):
        return sum([s.amount for s in self.schedules.filter(is_paid=True)])

class PaymentSchedule(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.loan.customer.full_name} - {self.date}"