from django.contrib import admin
from .models import Customer, Loan, PaymentSchedule, EmergencyLoan, EmergencyPaymentSchedule

# ================= PaymentSchedule Inline for Loan =================
class PaymentScheduleInline(admin.TabularInline):
    model = PaymentSchedule
    extra = 0
    readonly_fields = ('is_paid',)
    fields = ('date', 'amount', 'paid_amount', 'is_paid')
    can_delete = True

# ================= Loan Admin =================
@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('customer', 'loan_amount', 'balance', 'remaining_balance', 'interest_type', 'interest_value', 'payment_frequency', 'start_date', 'due_date')
    list_filter = ('interest_type', 'payment_frequency', 'start_date', 'due_date')
    search_fields = ('customer__full_name',)
    inlines = [PaymentScheduleInline]

# ================= EmergencyPaymentSchedule Inline for EmergencyLoan =================
class EmergencyPaymentScheduleInline(admin.TabularInline):
    model = EmergencyPaymentSchedule
    extra = 0
    readonly_fields = ('is_paid',)
    fields = ('date', 'amount', 'paid_amount', 'is_paid', 'payment_type')
    can_delete = True

# ================= EmergencyLoan Admin =================
@admin.register(EmergencyLoan)
class EmergencyLoanAdmin(admin.ModelAdmin):
    list_display = ('customer', 'loan_amount', 'remaining_principal', 'interest_percent', 'schedule_day', 'start_date', 'created_at')
    list_filter = ('schedule_day', 'start_date', 'created_at')
    search_fields = ('customer__full_name',)
    inlines = [EmergencyPaymentScheduleInline]

# ================= Customer Admin =================
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'contact_number', 'is_active')
    search_fields = ('full_name', 'contact_number')

# ================= PaymentSchedule Admin (optional, if you want standalone view) =================
@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('loan', 'date', 'amount', 'paid_amount', 'is_paid')
    list_filter = ('is_paid', 'date')
    search_fields = ('loan__customer__full_name',)

# ================= EmergencyPaymentSchedule Admin (optional) =================
@admin.register(EmergencyPaymentSchedule)
class EmergencyPaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('emergency_loan', 'date', 'amount', 'paid_amount', 'is_paid', 'payment_type')
    list_filter = ('is_paid', 'payment_type', 'date')
    search_fields = ('emergency_loan__customer__full_name',)