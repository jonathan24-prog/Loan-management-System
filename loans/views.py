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

def dashboard(request):
    today = date.today()

    # Total and active customers
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(
        loans__remaining_balance__gt=0
    ).distinct().count()

    # Monthly income (this month)
    monthly_income = PaymentSchedule.objects.filter(
        is_paid=True,
        date__year=today.year,
        date__month=today.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Loan analytics
    total_loans = Loan.objects.count()
    ongoing_loans = Loan.objects.filter(remaining_balance__gt=0).count()
    paid_loans = Loan.objects.filter(remaining_balance=0).count()
    overdue_payments = PaymentSchedule.objects.filter(
        is_paid=False,
        date__lt=today
    ).count()

    # Monthly income chart (last 12 months)
    monthly_data_qs = (
        PaymentSchedule.objects
        .filter(is_paid=True)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    chart_labels = [m['month'].strftime("%b %Y") for m in monthly_data_qs]
    chart_data = [float(m['total']) for m in monthly_data_qs]

    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'monthly_income': monthly_income,
        'total_loans': total_loans,
        'ongoing_loans': ongoing_loans,
        'paid_loans': paid_loans,
        'overdue_payments': overdue_payments,
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
from datetime import date  # ADD THIS

def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    loans = customer.loans.all()

    total_income = sum([loan.balance for loan in loans])

    # ✅ ADD THIS LOOP
    for loan in loans:
        if loan.start_date and loan.due_date:
            loan.total_days = (loan.due_date - loan.start_date).days + 1
            loan.days_left = (loan.due_date - date.today()).days

            # ✅ ADD THIS
            loan.days_overdue = abs(loan.days_left) if loan.days_left < 0 else 0
        else:
            loan.total_days = 0
            loan.days_left = 0
            loan.days_overdue = 0

    context = {
        'customer': customer,
        'loans': loans,
        'total_income': total_income,
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