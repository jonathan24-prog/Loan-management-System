from decimal import Decimal
from django.db import models
from loans.models import Loan, PaymentSchedule

count = 0

for loan in Loan.objects.all():
    total_paid = (
        PaymentSchedule.objects
        .filter(loan=loan)
        .aggregate(total=models.Sum('paid_amount'))['total']
    ) or Decimal('0.00')

    remaining = loan.balance - total_paid

    if remaining < 0:
        remaining = Decimal('0.00')

    loan.remaining_balance = remaining
    loan.save(update_fields=['remaining_balance'])

    count += 1

print(f"Fixed {count} loans")