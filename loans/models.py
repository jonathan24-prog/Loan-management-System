from django.db import models
from decimal import Decimal
from datetime import date

# 2026-04-11 06:15:55.758321

# ================= Customer =================
class Customer(models.Model):
    full_name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=20, blank=True, null=True)

    @property
    def is_active(self):
        has_regular = self.loans.filter(remaining_balance__gt=0).exists()

        has_emergency = self.emergency_loans.filter(
            remaining_principal__gt=0
        ).exists()

        return has_regular or has_emergency
        
    def __str__(self):
        return self.full_name


from django.db import models
from django.utils import timezone
# ================= Loan =================
class Loan(models.Model):
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

    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='loans'
    )

    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)

    interest_type = models.CharField(
        max_length=10,
        choices=INTEREST_TYPE_CHOICES,
        default='percent'
    )

    interest_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    payment_frequency = models.CharField(
        max_length=15,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default='daily'
    )

    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # 🟢 USER INPUT (when repayment starts)
    start_date = models.DateField()

    # 🔵 AUTO (when loan is created / money released)
    date_released = models.DateTimeField(default=timezone.now, editable=False)

    due_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            # compute total loan balance on creation
            if self.interest_type == 'percent':
                self.balance = self.loan_amount + (
                    self.loan_amount * self.interest_value / 100
                )
            else:
                self.balance = self.loan_amount + self.interest_value

            self.remaining_balance = self.balance

        super().save(*args, **kwargs)


class OldLoan(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='old_loans')
    
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Old Loan - {self.customer.full_name}"


class OldLoanPayment(models.Model):
    old_loan = models.ForeignKey(OldLoan, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)



# ================= Payment Schedule =================
from django.db import models
from django.utils import timezone

class PaymentSchedule(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)

    # ✅ NEW FIELD (actual payment timestamp)
    paid_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # auto mark paid
        self.is_paid = self.paid_amount >= self.amount

        # set payment timestamp only when first fully paid
        if self.is_paid and not self.paid_at:
            self.paid_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan.customer.full_name} - {self.date}"


# ================= Emergency Loan (unchanged) =================
class EmergencyLoan(models.Model):
    SCHEDULE_CHOICES = [
        ('Monday','Monday'), ('Tuesday','Tuesday'), ('Wednesday','Wednesday'),
        ('Thursday','Thursday'), ('Friday','Friday'), ('Saturday','Saturday'), ('Sunday','Sunday'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='emergency_loans')
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_principal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_percent = models.DecimalField(max_digits=5, decimal_places=2)
    schedule_day = models.CharField(max_length=10, choices=SCHEDULE_CHOICES)
    start_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.remaining_principal = self.loan_amount
        super().save(*args, **kwargs)

    def current_weekly_interest(self):
        return round(self.remaining_principal * self.interest_percent / 100, 2)

    def __str__(self):
        return f"{self.customer.full_name} - Emergency Loan ({self.loan_amount})"


class EmergencyPaymentSchedule(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('interest', 'Interest'),
        ('principal', 'Principal'),
    ]

    emergency_loan = models.ForeignKey(
        EmergencyLoan,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_TYPE_CHOICES,
        default='interest'
    )

    # ✅ NEW FIELD (timestamp)
    paid_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # auto mark paid
        self.is_paid = self.paid_amount >= self.amount

        # set timestamp only once when first fully paid
        if self.is_paid and not self.paid_at:
            self.paid_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.emergency_loan.customer.full_name} - {self.date} ({self.payment_type})"