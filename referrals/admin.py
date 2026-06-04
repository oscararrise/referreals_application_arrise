from django.contrib import admin
from .models import Referral
from .models import EmployeeDirectoryHiBob

admin.site.register(EmployeeDirectoryHiBob)

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        'candidate_name',
        'candidate_email',
        'status',
        'referrer',
        'referred_date'
    )

    list_filter = ('status', 'country', 'role_name')

    search_fields = ('candidate_name', 'candidate_email')