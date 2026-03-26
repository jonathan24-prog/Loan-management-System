from django.urls import path
from . import views

urlpatterns = [

path('', views.login_view, name='login'),

path('dashboard/', views.dashboard, name='dashboard'),
path('customers/', views.customers, name='customers'),
path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
# urls.py
path('customer/<int:pk>/add-loan/', views.add_loan, name='add_loan'),
path('customer/<int:pk>/add-emergency-loan/', views.add_emergency_loan, name='add_emergency_loan'),
path('customer/<int:pk>/reloan/', views.reloan, name='reloan'),
path('payment/<int:pk>/paid/', views.mark_payment_paid, name='mark_payment_paid'),
path('emergency-payment/<int:pk>/paid/', views.mark_emergency_paid, name='mark_emergency_paid'),

path('logout/', views.logout_view, name='logout'),

]