from django.urls import path
from .views import create_referral, my_referrals, home

urlpatterns = [
    path('', home, name='home'),
    path('new/', create_referral, name='create_referral'),
    path('my/', my_referrals, name='my_referrals'),
]