from django.urls import path

from .views import login_view, logout_view, verify_otp_view


urlpatterns = [
    path("login/", login_view, name="login"),
    path("verify-otp/", verify_otp_view, name="verify_otp"),
    path("logout/", logout_view, name="logout"),
]