# ================= IMPORTS =================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from datetime import timedelta

from .models import Customer, Loan, PaymentSchedule
from .forms import CustomerForm, LoanForm


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
from datetime import date
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
import json

from django.utils import timezone
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear,  TruncHour
from django.db.models import Sum
import json
from datetime import date, timedelta

def dashboard(request):
    today = date.today()
    filter_type = request.GET.get('filter', 'month')  # default = month

    # DATE FILTER RANGE
    if filter_type == 'day':
        payments = PaymentSchedule.objects.filter(date=today)

    elif filter_type == 'week':
        start_week = today - timedelta(days=today.weekday())
        payments = PaymentSchedule.objects.filter(date__gte=start_week)

    elif filter_type == 'year':
        payments = PaymentSchedule.objects.filter(date__year=today.year)

    else:  # month (default)
        payments = PaymentSchedule.objects.filter(
            date__year=today.year,
            date__month=today.month
        )

    payments = payments.filter(is_paid=True)

    # ✅ TOTAL COLLECTION (filtered)
    total_collection = payments.aggregate(total=Sum('amount'))['total'] or 0

    # ✅ TOTAL RELEASED (filtered)
    if filter_type == 'day':
        loans = Loan.objects.filter(start_date=today)
    elif filter_type == 'week':
        loans = Loan.objects.filter(start_date__gte=start_week)
    elif filter_type == 'year':
        loans = Loan.objects.filter(start_date__year=today.year)
    else:
        loans = Loan.objects.filter(
            start_date__year=today.year,
            start_date__month=today.month
        )

    total_released = loans.aggregate(total=Sum('loan_amount'))['total'] or 0

    # ✅ TOTAL INTEREST (GLOBAL)
    total_interest_collected = total_collection - total_released
    if total_interest_collected < 0:
        total_interest_collected = 0

    # EXISTING STATS
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(
        loans__remaining_balance__gt=0
    ).distinct().count()

    total_loans = Loan.objects.count()
    ongoing_loans = Loan.objects.filter(remaining_balance__gt=0).count()
    paid_loans = Loan.objects.filter(remaining_balance=0).count()

    overdue_payments = PaymentSchedule.objects.filter(
        is_paid=False,
        date__lt=today
    ).count()

    # 📊 CHART GROUPING BASED ON FILTER
    if filter_type == 'day':
        trunc = TruncDay('date') # optional if you want hourly
    elif filter_type == 'week':
        trunc = TruncDay('date')
    elif filter_type == 'year':
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
        'monthly_income': total_collection,  # reuse

        'total_loans': total_loans,
        'ongoing_loans': ongoing_loans,
        'paid_loans': paid_loans,
        'overdue_payments': overdue_payments,

        # ✅ NEW
        'total_collection': total_collection,
        'total_released': total_released,
        'total_interest_collected': total_interest_collected,
        'filter_type': filter_type,

        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'loans/dashboard.html', context)

# ================= CUSTOMERS =================
from django.db.models import Q  # ADD THIS IMPORT

from django.db.models import Q

def customers(request):
    query = request.GET.get('q')

    customers = Customer.objects.all().prefetch_related('loans')

    # 🔍 SEARCH
    if query:
        customers = customers.filter(
            Q(full_name__icontains=query) |
            Q(contact_number__icontains=query)
        )

    # 🧮 COUNTS
    total_customers = customers.count()

    active_customers = Customer.objects.filter(
        loans__remaining_balance__gt=0
    ).distinct().count()

    # ➕ ADD CUSTOMER
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


# ================= CUSTOMER DETAILS =================

from django.shortcuts import get_object_or_404, render
from django.db.models import Sum
from datetime import date
from .models import Customer, Loan, EmergencyLoan

def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    loans = customer.loans.all()
    
    # Fetch emergency loans separately
    emergency_loans = customer.emergency_loans.prefetch_related('schedules').all()

    total_income = sum([loan.balance for loan in loans])

    total_interest_collected = 0
    total_collection = 0   # ALL money collected (principal + interest)
    total_released = 0     # ONLY principal

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


    emergency_loans = customer.emergency_loans.prefetch_related('schedules').all()

    for e_loan in emergency_loans:
        # Total interest paid so far
        e_loan.total_interest_paid = e_loan.schedules.filter(is_paid=True).aggregate(
            total=Sum('amount')
        )['total'] or 0

        e_total_paid = e_loan.schedules.filter(is_paid=True).aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_collection += e_total_paid

        e_interest_paid = e_loan.schedules.filter(is_paid=True, payment_type='interest').aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_interest_collected += e_interest_paid

        total_released += e_loan.loan_amount

        # Current weekly interest (still unpaid interest for next week)
        e_loan.current_weekly_interest = round(
            e_loan.remaining_principal * e_loan.interest_percent / 100, 2
        )

    context = {
        'customer': customer,
        'loans': loans,
        'emergency_loans': emergency_loans,  # ✅ Added for template
        'total_income': total_income,
        'total_interest_collected': total_interest_collected,
        'total_collection': total_collection,
        'total_released': total_released,
    }

    return render(request, 'loans/customer_detail.html', context)


# ================= LOANS =================
def add_loan(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer
            loan.save()

            delta = (loan.due_date - loan.start_date).days + 1
            daily_amount = loan.balance / delta if delta > 0 else loan.balance

            for i in range(delta):
                PaymentSchedule.objects.create(
                    loan=loan,
                    date=loan.start_date + timedelta(days=i),
                    amount=daily_amount
                )

            return redirect('customer_detail', pk=customer.pk)
    else:
        form = LoanForm()

    return render(request, 'loans/add_loan.html', {'form': form, 'customer': customer})


from django.shortcuts import render, get_object_or_404, redirect
from datetime import timedelta
from .models import Customer, PaymentSchedule
from .forms import EmergencyLoanForm  # ✅ use correct form
from django.shortcuts import render, get_object_or_404, redirect
from datetime import timedelta
from .models import Customer, EmergencyLoan, EmergencyPaymentSchedule
from .forms import EmergencyLoanForm, PrincipalPaymentForm
from django import forms
from .models import Customer, Loan, EmergencyLoan, EmergencyPaymentSchedule

def add_emergency_loan(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = EmergencyLoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer

            # ✅ Compute total balance (principal + interest)
            total_balance = loan.loan_amount + (
                loan.loan_amount * loan.interest_percent / 100
            )

            loan.remaining_balance = total_balance
            loan.save()

            # ✅ Compute WEEKLY INTEREST ONLY
            interest_amount = loan.loan_amount * loan.interest_percent / 100

            # ✅ First payment only
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


# ================= PAYMENTS =================
def mark_payment_paid(request, pk):
    payment = get_object_or_404(PaymentSchedule, pk=pk)

    if not payment.is_paid:
        payment.is_paid = True
        payment.save()

        loan = payment.loan
        loan.remaining_balance -= payment.amount

        if loan.remaining_balance < 0:
            loan.remaining_balance = 0

        loan.save(update_fields=['remaining_balance'])

    return redirect('customer_detail', pk=payment.loan.customer.pk)



def mark_emergency_paid(request, pk):
    payment = get_object_or_404(EmergencyPaymentSchedule, pk=pk)
    loan = payment.emergency_loan

    if not payment.is_paid:
        payment.is_paid = True
        payment.paid_amount = payment.amount
        payment.save()

        if payment.payment_type == 'interest':
            # Interest payment: only affects interest schedule, principal stays same
            pass  # nothing to change in principal
        else:  # principal payment
            loan.remaining_principal -= payment.amount
            if loan.remaining_principal < 0:
                loan.remaining_principal = 0
            loan.save()

        # Generate next interest payment based on remaining principal
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
                # create a principal payment record
                EmergencyPaymentSchedule.objects.create(
                    emergency_loan=loan,
                    date=date.today(),
                    amount=amount,
                    payment_type='principal',
                    is_paid=True,
                    paid_amount=amount
                )
                # deduct principal
                loan.remaining_principal -= amount
                if loan.remaining_principal < 0:
                    loan.remaining_principal = 0
                loan.save()
            return redirect('customer_detail', pk=loan.customer.pk)
    else:
        form = PrincipalPaymentForm()

    return render(request, 'loans/pay_principal.html', {'form': form, 'loan': loan})