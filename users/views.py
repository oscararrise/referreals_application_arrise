import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from .models import Administrador, CustomUser, EmailOTP
from referrals.models import EmployeeDirectoryHiBob

from .models import EmailOTP
from .services import send_otp_email


def login_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "login.html")

        employee_exists = EmployeeDirectoryHiBob.objects.filter(
            email__iexact=email
        ).exists()

        if not employee_exists:
            messages.error(request, "Email not found in the employee directory.")
            return render(request, "login.html")

        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = timezone.now() + timedelta(minutes=5)

        EmailOTP.objects.filter(email__iexact=email).delete()

        EmailOTP.objects.create(
            email=email,
            code=otp_code,
            expires_at=expires_at,
        )

        try:
            send_otp_email(
                to_email=email,
                otp_code=otp_code,
            )
        except Exception:
            EmailOTP.objects.filter(email__iexact=email).delete()
            messages.error(
                request,
                "We could not send the verification code. Please try again."
            )
            return render(request, "login.html")

        request.session["otp_email"] = email

        return redirect("verify_otp")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect("/login/")

def verify_otp_view(request):
    email = request.session.get("otp_email")

    if not email:
        messages.error(request, "Your verification session has expired.")
        return redirect("login")

    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()

        otp = EmailOTP.objects.filter(
            email__iexact=email,
            code=code,
        ).order_by("-created_at").first()

        if not otp:
            messages.error(request, "Invalid verification code.")
            return render(
                request,
                "verify_otp.html",
                {"email": email},
            )

        if otp.is_expired():
            otp.delete()
            request.session.pop("otp_email", None)

            messages.error(
                request,
                "The verification code has expired. Request a new one."
            )
            return redirect("login")

        is_admin = Administrador.objects.filter(
            email__iexact=email,
            is_active=True,
        ).exists()

        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "role": "admin" if is_admin else "user",
                "is_staff": is_admin,
                "is_active": True,
            },
        )

        user.role = "admin" if is_admin else "user"
        user.is_staff = is_admin
        user.is_active = True

        if created:
            user.set_unusable_password()

        user.save()

        login(request, user)

        otp.delete()
        request.session.pop("otp_email", None)

        return redirect("home")

    return render(
        request,
        "verify_otp.html",
        {"email": email},
    )