# ================= IMPORTS =================
from datetime import date, timedelta
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone

from .models import (
    Customer,
    Loan,
    PaymentSchedule,
    EmergencyLoan,
    EmergencyPaymentSchedule
)
from .forms import (
    CustomerForm,
    LoanForm,
    EmergencyLoanForm,
    PrincipalPaymentForm
)


# ================= AUTH =================
def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')

    return render(request, 'loans/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ================= DASHBOARD =================
def dashboard(request):
    today = date.today()
    filter_type = request.GET.get('filter', 'month')
    payments = PaymentSchedule.objects.filter(
    is_paid=True,
    paid_at__isnull=False
)

    # DATE FILTER
    if filter_type == 'day':
        payments = payments.filter(paid_at__date=today)

    elif filter_type == 'week':
        start_week = today - timedelta(days=today.weekday())
        payments = payments.filter(paid_at__date__gte=start_week)

    elif filter_type == 'year':
        payments = payments.filter(paid_at__year=today.year)

    else:
        payments = payments.filter(
            paid_at__year=today.year,
            paid_at__month=today.month
        )

    payments = payments.filter(is_paid=True)

    # TOTAL COLLECTION
    total_collection = payments.aggregate(total=Sum('amount'))['total'] or 0
    
    emergency_collection = EmergencyPaymentSchedule.objects.filter(
        is_paid=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_collection = total_collection + emergency_collection

    # TOTAL RELEASED
    if filter_type == 'day':
        loans = Loan.objects.filter(date_released__date=today)

    elif filter_type == 'week':
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        loans = Loan.objects.filter(
            date_released__date__gte=start_week,
            date_released__date__lte=end_week
        )

    elif filter_type == 'month':   # ✅ EXPLICIT MONTH FILTER
        loans = Loan.objects.filter(
            date_released__year=today.year,
            date_released__month=today.month
        )

    elif filter_type == 'year':
        loans = Loan.objects.filter(date_released__year=today.year)

    else:
        # default = current month
        loans = Loan.objects.filter(
            date_released__year=today.year,
            date_released__month=today.month
        )


    emergency_released = EmergencyLoan.objects.all().aggregate(
        total=Sum('loan_amount')
    )['total'] or 0

    total_released = (loans.aggregate(total=Sum('loan_amount'))['total'] or 0) + emergency_released

    # TOTAL INTEREST
    regular_paid = PaymentSchedule.objects.filter(
        is_paid=True
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    regular_released = Loan.objects.aggregate(
        total=Sum('loan_amount')
    )['total'] or 0

    regular_interest = regular_paid - regular_released

    if regular_interest < 0:
        regular_interest = 0


    # ---------------- EMERGENCY LOANS ----------------
    emergency_interest = EmergencyPaymentSchedule.objects.filter(
        is_paid=True,
        payment_type='interest'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0


    # ---------------- FINAL TOTAL ----------------
    total_interest_collected = regular_interest + emergency_interest

    # STATS
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(
        loans__remaining_balance__gt=0
    ).distinct().count()

    total_loans = Loan.objects.count()


    regular_ongoing = Loan.objects.filter(remaining_balance__gt=0).count()
    emergency_ongoing = EmergencyLoan.objects.filter(remaining_principal__gt=0).count()

    ongoing_loans = regular_ongoing + emergency_ongoing
    
    paid_loans = Loan.objects.filter(remaining_balance=0).count()

    overdue_payments = PaymentSchedule.objects.filter(
        is_paid=False,
        date__lt=today
    ).count()

    # CHART GROUPING
    if filter_type == 'year':
        trunc = TruncMonth('date')
    else:
        trunc = TruncDay('date')

    chart_qs = (
        payments
        .annotate(period=trunc)
        .values('period')
        .annotate(total=Sum('amount'))
        .order_by('period')
    )

    chart_labels = [c['period'].strftime("%b %d") for c in chart_qs]
    chart_data = [float(c['total']) for c in chart_qs]

    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'monthly_income': total_collection,

        'total_loans': total_loans,
        'ongoing_loans': ongoing_loans,
        'paid_loans': paid_loans,
        'overdue_payments': overdue_payments,

        'total_collection': total_collection,
        'total_released': total_released,
        'total_interest_collected': total_interest_collected,
        'filter_type': filter_type,

        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'loans/dashboard.html', context)


# ================= CUSTOMERS =================
def customers(request):
    query = request.GET.get('q')
    today = date.today()

    customers = Customer.objects.all().prefetch_related('loans__schedules', 'emergency_loans__schedules')

    if query:
        customers = customers.filter(
            Q(full_name__icontains=query) |
            Q(contact_number__icontains=query)
        )

    total_customers = customers.count()

    active_customers = Customer.objects.filter(
        loans__remaining_balance__gt=0
    ).distinct().count()

    # -------------------- TODAY'S STATUS --------------------
    for customer in customers:
        today = date.today()
        customer.today_status = "Unpaid"  # default

        # Regular loan schedules for today
        regular_schedules_today = PaymentSchedule.objects.filter(
            loan__customer=customer,
            date=today
        )

        # Emergency loan schedules for today
        emergency_schedules_today = EmergencyPaymentSchedule.objects.filter(
            emergency_loan__customer=customer,
            date=today
        )

        # Combine all schedules
        all_schedules_today = list(regular_schedules_today) + list(emergency_schedules_today)

        if all_schedules_today:  # If customer has schedules today
            # Check if **all** are paid
            if all(s.is_paid for s in all_schedules_today):
                customer.today_status = "Paid"
            else:
                customer.today_status = "Unpaid"
        else:
            customer.today_status = "no schedule"  # No schedules today
    # ---------------------------------------------------------

    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customers')
    else:
        form = CustomerForm()

    context = {
        'form': form,
        'customers': customers,
        'total_customers': total_customers,
        'active_customers': active_customers,
    }

    return render(request, 'loans/customers.html', context)


def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == "POST":
        customer.delete()
        messages.success(request, f"{customer.full_name} has been deleted.")
        return redirect('customers')

    return render(request, 'loans/customer_confirm_delete.html', {'customer': customer})


# ================= CUSTOMER DETAIL =================
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    loans = customer.loans.all().order_by('-id')
    emergency_loans = customer.emergency_loans.prefetch_related('schedules').all().order_by('-id')

    total_income = sum([loan.balance for loan in loans])

    total_interest_collected = 0
    total_collection = 0
    total_released = 0

    for loan in loans:
        if loan.start_date and loan.due_date:
            loan.total_days = (loan.due_date - loan.start_date).days + 1
            loan.days_left = (loan.due_date - date.today()).days
            loan.days_overdue = abs(loan.days_left) if loan.days_left < 0 else 0
        else:
            loan.total_days = 0
            loan.days_left = 0
            loan.days_overdue = 0

        total_released += loan.loan_amount

        total_paid = loan.schedules.filter(is_paid=True).aggregate(
            total=Sum('amount')
        )['total'] or 0

        total_collection += total_paid

        interest = total_paid - loan.loan_amount
        if interest > 0:
            total_interest_collected += interest

    for e_loan in emergency_loans:
        e_total_paid = e_loan.schedules.filter(is_paid=True).aggregate(
            total=Sum('amount')
        )['total'] or 0

        total_collection += e_total_paid

        e_interest_paid = e_loan.schedules.filter(
            is_paid=True,
            payment_type='interest'
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_interest_collected += e_interest_paid
        total_released += e_loan.loan_amount

        e_loan.total_interest_paid = e_total_paid

        e_loan.current_weekly_interest = round(
            e_loan.remaining_principal * e_loan.interest_percent / 100, 2
        )

    context = {
        'customer': customer,
        'loans': loans,
        'emergency_loans': emergency_loans,
        'total_income': total_income,
        'total_interest_collected': total_interest_collected,
        'total_collection': total_collection,
        'total_released': total_released,
    }

    return render(request, 'loans/customer_detail.html', context)


# ================= LOANS =================
from datetime import timedelta
from dateutil.relativedelta import relativedelta  # install if needed

from math import ceil
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import calendar

def add_loan(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer
            loan.save()

            schedules = []
            current_date = loan.start_date

            # ================= FIXED PAYMENT MODE =================
            if loan.payment_amount and loan.payment_amount > 0:
                total_payments = ceil(loan.balance / loan.payment_amount)

                for i in range(total_payments):
                    if loan.payment_frequency == 'daily':
                        pay_date = current_date + timedelta(days=i)

                    elif loan.payment_frequency == 'weekly':
                        pay_date = current_date + timedelta(days=7 * i)

                    elif loan.payment_frequency == 'semi_monthly':
                        base_date = current_date + relativedelta(months=i // 2)

                        if i % 2 == 0:
                            pay_date = base_date.replace(day=15)
                        else:
                            last_day = calendar.monthrange(base_date.year, base_date.month)[1]
                            pay_date = base_date.replace(day=last_day)

                    elif loan.payment_frequency == 'monthly':
                        pay_date = current_date + relativedelta(months=i)

                    # LAST PAYMENT ADJUSTMENT
                    if i == total_payments - 1:
                        remaining = loan.balance - (loan.payment_amount * (total_payments - 1))
                        amount = remaining
                    else:
                        amount = loan.payment_amount

                    schedules.append(PaymentSchedule(
                        loan=loan,
                        date=pay_date,
                        amount=amount
                    ))

                # ✅ AUTO SET DUE DATE
                loan.due_date = schedules[-1].date
                loan.save(update_fields=['due_date'])

            # ================= NORMAL MODE =================
            else:
                current_date = loan.start_date

                if loan.payment_frequency == 'daily':
                    delta = (loan.due_date - loan.start_date).days + 1
                    amount = loan.balance / delta

                    for i in range(delta):
                        schedules.append(PaymentSchedule(
                            loan=loan,
                            date=current_date,
                            amount=amount
                        ))
                        current_date += timedelta(days=1)

                elif loan.payment_frequency == 'weekly':
                    dates = []
                    while current_date <= loan.due_date:
                        dates.append(current_date)
                        current_date += timedelta(days=7)

                    amount = loan.balance / len(dates)

                    for d in dates:
                        schedules.append(PaymentSchedule(
                            loan=loan,
                            date=d,
                            amount=amount
                        ))

                elif loan.payment_frequency == 'semi_monthly':
                    

                    dates = []
                    temp_date = current_date

                    while temp_date <= loan.due_date:
                        year = temp_date.year
                        month = temp_date.month

                        # 15th
                        fifteenth = temp_date.replace(day=15)

                        # End of month
                        last_day = calendar.monthrange(year, month)[1]
                        end_month = temp_date.replace(day=last_day)

                        # Add 15th if valid
                        if fifteenth >= current_date and fifteenth <= loan.due_date:
                            dates.append(fifteenth)

                        # Add end of month if valid
                        if end_month >= current_date and end_month <= loan.due_date:
                            dates.append(end_month)

                        # Move to next month
                        temp_date += relativedelta(months=1)

                    # Remove duplicates & sort (important!)
                    dates = sorted(list(set(dates)))

                    amount = loan.balance / len(dates)

                    for d in dates:
                        schedules.append(PaymentSchedule(
                            loan=loan,
                            date=d,
                            amount=amount
                        ))

                elif loan.payment_frequency == 'monthly':
                    dates = []
                    while current_date <= loan.due_date:
                        dates.append(current_date)
                        current_date += relativedelta(months=1)

                    amount = loan.balance / len(dates)

                    for d in dates:
                        schedules.append(PaymentSchedule(
                            loan=loan,
                            date=d,
                            amount=amount
                        ))

            PaymentSchedule.objects.bulk_create(schedules)

            return redirect('customer_detail', pk=customer.pk)

    else:
        form = LoanForm()

    return render(request, 'loans/add_loan.html', {
        'form': form,
        'customer': customer,
     
    })
    
def reloan(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    existing_loan = customer.loans.filter(balance__gt=0).first()

    if existing_loan:
        return render(request, 'loans/reloan_error.html', {
            'customer': customer,
            'loan': existing_loan
        })

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer
            loan.balance = loan.loan_amount
            loan.save()

            delta = (loan.due_date - loan.start_date).days + 1
            daily_amount = loan.balance / delta if delta > 0 else loan.balance

            for i in range(delta):
                PaymentSchedule.objects.create(
                    loan=loan,
                    date=loan.start_date + timedelta(days=i),
                    amount=daily_amount
                )

            return redirect('customer_detail', pk=pk)
    else:
        form = LoanForm()

    return render(request, 'loans/reloan.html', {
        'form': form,
        'customer': customer
    })


def add_emergency_loan(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = EmergencyLoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer

            total_balance = loan.loan_amount + (
                loan.loan_amount * loan.interest_percent / 100
            )

            loan.remaining_balance = total_balance
            loan.save()

            interest_amount = loan.loan_amount * loan.interest_percent / 100

            EmergencyPaymentSchedule.objects.create(
                emergency_loan=loan,
                date=loan.start_date,
                amount=interest_amount
            )

            return redirect('customer_detail', pk=customer.pk)
    else:
        form = EmergencyLoanForm()

    return render(request, 'loans/add_emergency_loan.html', {
        'form': form,
        'customer': customer
    })


# ================= PAYMENTS =================
from decimal import Decimal

# def mark_payment_paid(request, pk):
#     payment = get_object_or_404(PaymentSchedule, pk=pk)
#     loan = payment.loan

#     if request.method == 'POST':
#         # Get the amount entered by user and convert to Decimal
#         try:
#             amount = Decimal(request.POST.get('paid_amount', '0'))
#         except:
#             messages.error(request, "Invalid amount entered.")
#             return redirect('customer_detail', pk=loan.customer.pk)

#         if amount <= 0:
#             messages.error(request, "Amount must be greater than zero.")
#             return redirect('customer_detail', pk=loan.customer.pk)

#         # Initialize paid_amount if None
#         if payment.paid_amount is None:
#             payment.paid_amount = Decimal('0.00')

#         # Update paid_amount
#         payment.paid_amount += amount

#         # Check if schedule is fully paid
#         if payment.paid_amount >= payment.amount:
#             payment.is_paid = True
#             payment.paid_amount = payment.amount  # prevent overpayment

#         payment.save()

#         # Update loan remaining balance
#         loan.remaining_balance -= amount
#         if loan.remaining_balance < 0:
#             loan.remaining_balance = 0
#         loan.save(update_fields=['remaining_balance'])

#         messages.success(request, f"Payment of ₱{amount} recorded successfully.")
#         return redirect('customer_detail', pk=loan.customer.pk)

#     # GET request: show a form to enter partial payment
#     return render(request, 'loans/mark_payment.html', {
#         'payment': payment
#     })



from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import PaymentSchedule

from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone

def mark_payment_paid(request, pk):
    payment = get_object_or_404(PaymentSchedule, pk=pk)
    loan = payment.loan

    if request.method == 'POST':
        full_payment = request.POST.get('full_payment') == 'on'

        if full_payment:
            amount = payment.amount
        else:
            try:
                amount = Decimal(request.POST.get('paid_amount', '0'))
            except:
                messages.error(request, "Invalid amount entered.")
                return redirect('customer_detail', pk=loan.customer.pk)

            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect('customer_detail', pk=loan.customer.pk)

        # initialize if empty
        if payment.paid_amount is None:
            payment.paid_amount = Decimal('0.00')

        # update payment
        payment.paid_amount += amount

        # set timestamp when first payment happens
        if not payment.paid_at:
            payment.paid_at = timezone.now()

        # mark fully paid
        if payment.paid_amount >= payment.amount:
            payment.is_paid = True
            payment.paid_amount = payment.amount

        payment.save()

        # update loan balance
        loan.remaining_balance -= amount
        if loan.remaining_balance < 0:
            loan.remaining_balance = 0
        loan.save(update_fields=['remaining_balance'])

        messages.success(request, f"Payment of ₱{amount} recorded successfully.")
        return redirect('customer_detail', pk=loan.customer.pk)

        

    return render(request, 'loans/mark_payment.html', {
        'payment': payment
    })

def mark_emergency_paid(request, pk):
    payment = get_object_or_404(EmergencyPaymentSchedule, pk=pk)
    loan = payment.emergency_loan

    if not payment.is_paid:
        payment.is_paid = True
        payment.paid_amount = payment.amount

        # ✅ SET PAYMENT TIME
        if not payment.paid_at:
            payment.paid_at = timezone.now()

        payment.save()

        if payment.payment_type == 'principal':
            loan.remaining_principal -= payment.amount
            if loan.remaining_principal < 0:
                loan.remaining_principal = 0
            loan.save()

        if payment.payment_type == 'interest' and loan.remaining_principal > 0:
            next_date = payment.date + timedelta(days=7)

            EmergencyPaymentSchedule.objects.create(
                emergency_loan=loan,
                date=next_date,
                amount=loan.current_weekly_interest(),
                payment_type='interest'
            )

    return redirect('customer_detail', pk=loan.customer.pk)

def pay_principal(request, loan_id):
    loan = get_object_or_404(EmergencyLoan, pk=loan_id)

    if request.method == 'POST':
        form = PrincipalPaymentForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']

            if amount > 0 and loan.remaining_principal > 0:
                EmergencyPaymentSchedule.objects.create(
                    emergency_loan=loan,
                    date=date.today(),
                    amount=amount,
                    payment_type='principal',
                    is_paid=True,
                    paid_amount=amount
                )

                loan.remaining_principal -= amount
                if loan.remaining_principal < 0:
                    loan.remaining_principal = 0

                loan.save()

            return redirect('customer_detail', pk=loan.customer.pk)
    else:
        form = PrincipalPaymentForm()

    return render(request, 'loans/pay_principal.html', {
        'form': form,
        'loan': loan
    })