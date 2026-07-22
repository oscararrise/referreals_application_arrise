from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("user", "User"),
        ("recruiter", "Recruiter"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")
    country = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]


class Administrador(models.Model):
    hibob_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    known_as_name = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "administradores"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} - {self.email}"


class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_otps"
        ordering = ["-created_at"]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.email} - expires at {self.expires_at}"