from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    ordering = ('email',)
    search_fields = ('email', 'username')

    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'country', 'department')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('email', 'role', 'country', 'department')}),
    )