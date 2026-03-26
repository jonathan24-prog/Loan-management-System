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


class EmergencyLoan(models.Model):
    SCHEDULE_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='emergency_loans')

    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_percent = models.DecimalField(max_digits=5, decimal_places=2)

    schedule_day = models.CharField(max_length=10, choices=SCHEDULE_CHOICES)
    start_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.full_name} - Emergency Loan ({self.loan_amount})"

    # ✅ Calculate total payable (principal + interest)
    def total_payable(self):
        return self.loan_amount + (self.loan_amount * self.interest_percent / 100)

    # ✅ Optional: Example weekly due date generator
    def next_due_date(self):
        if not self.start_date:
            return None

        days_map = {
            'Monday': 0,
            'Tuesday': 1,
            'Wednesday': 2,
            'Thursday': 3,
            'Friday': 4,
            'Saturday': 5,
            'Sunday': 6,
        }

        start_weekday = self.start_date.weekday()
        target_weekday = days_map[self.schedule_day]

        days_ahead = target_weekday - start_weekday
        if days_ahead <= 0:
            days_ahead += 7

        return self.start_date + timedelta(days=days_ahead)
    
    def save(self, *args, **kwargs):
        if not self.pk:
            total = self.loan_amount + (self.loan_amount * self.interest_percent / 100)
            self.remaining_balance = total
        super().save(*args, **kwargs)

class EmergencyPaymentSchedule(models.Model):
    emergency_loan = models.ForeignKey(EmergencyLoan, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.emergency_loan.customer.full_name} - {self.date}"