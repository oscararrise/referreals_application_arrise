from django.db import models
from django.conf import settings


class EmployeeDirectoryHiBob(models.Model):
    employee_id = models.CharField(max_length=50)
    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)

    site_country = models.CharField(max_length=100, blank=True, null=True)
    site = models.CharField(max_length=100, blank=True, null=True)

    business_unit = models.CharField(max_length=100, blank=True, null=True)
    entity = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    sub_department = models.CharField(max_length=100, blank=True, null=True)

    job_title = models.CharField(max_length=255, blank=True, null=True)
    employment_type = models.CharField(max_length=100, blank=True, null=True)

    lifecycle_status = models.CharField(max_length=100, blank=True, null=True)

    start_date = models.DateField(blank=True, null=True)
    termination_date = models.DateField(blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)
    candidate_jobvite_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.email} - {self.employee_id}"


class Referral(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("screening", "Screening"),
        ("interview", "Interview"),
        ("offer", "Offer"),
        ("hired", "Hired"),
        ("rejected", "Rejected"),
    ]

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals",
    )

    candidate_name = models.CharField(max_length=255)
    candidate_email = models.EmailField()
    candidate_phone = models.CharField(max_length=50, blank=True, null=True)

    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True, null=True)

    role_name = models.CharField(max_length=100)
    role_type = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
    )

    bonus_eligible = models.BooleanField(default=False)
    referred_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    hired_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.candidate_name} - {self.status}"


class JobviteApplication(models.Model):
    application_eid = models.CharField(max_length=120, unique=True)
    candidate_eid = models.CharField(max_length=120, blank=True, null=True)

    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    mobile = models.CharField(max_length=100, blank=True, null=True)

    source = models.TextField(blank=True, null=True)
    source_type = models.CharField(max_length=150, blank=True, null=True)
    hibob_id = models.CharField(max_length=100, blank=True, null=True)

    workflow_state = models.CharField(max_length=150, blank=True, null=True)
    workflow_state_eid = models.CharField(max_length=120, blank=True, null=True)

    sent_date = models.DateTimeField(blank=True, null=True)
    last_updated_date = models.DateTimeField(blank=True, null=True)

    job_eid = models.CharField(max_length=120, blank=True, null=True)
    requisition_id = models.CharField(max_length=100, blank=True, null=True)
    job_title = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=150, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    posting_type = models.CharField(max_length=100, blank=True, null=True)

    raw_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobvite_applications"
        indexes = [
            models.Index(fields=["hibob_id"]),
            models.Index(fields=["email"]),
            models.Index(fields=["requisition_id"]),
            models.Index(fields=["last_updated_date"]),
        ]

    def __str__(self):
        return f"{self.application_eid} - {self.email or 'no-email'}"


class JobviteRequisitionReferralDetail(models.Model):
    req_id = models.CharField(max_length=100, db_index=True)

    recruiter_name = models.CharField(max_length=255, blank=True, null=True)
    workflow_title = models.CharField(max_length=255, blank=True, null=True)
    hiring_manager_name = models.CharField(max_length=255, blank=True, null=True)
    interviewer_full_name = models.CharField(max_length=255, blank=True, null=True)

    raw_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobvite_requisition_referral_details"
        indexes = [
            models.Index(fields=["req_id"]),
            models.Index(fields=["recruiter_name"]),
            models.Index(fields=["hiring_manager_name"]),
            models.Index(fields=["interviewer_full_name"]),
        ]

    def __str__(self):
        return f"{self.req_id} - {self.interviewer_full_name or 'No interviewer'}"


class ReferralBonusRule(models.Model):
    location_of_the_referral = models.CharField(max_length=255, blank=True, null=True)
    sub_department = models.CharField(max_length=255, blank=True, null=True)
    workflow_title = models.CharField(max_length=255, blank=True, null=True)
    presenter_shuffler = models.CharField(max_length=255, blank=True, null=True)
    table_language = models.CharField(max_length=255, blank=True, null=True)
    full_time_part_time = models.CharField(max_length=255, blank=True, null=True)

    date_effective = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)

    bonus_amount_eur_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    bonus_amount_eur_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    pay_type = models.CharField(max_length=100, blank=True, null=True)

    special_campaign_1st_installment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    special_campaign_2nd_installment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    special_campaign_3rd_installment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    specificity = models.IntegerField(blank=True, null=True)
    rule_rank = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        db_index=True,
    )

    raw_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_bonus_rules"
        indexes = [
            models.Index(fields=["location_of_the_referral"]),
            models.Index(fields=["workflow_title"]),
            models.Index(fields=["sub_department"]),
            models.Index(fields=["date_effective"]),
            models.Index(fields=["date_end"]),
            models.Index(fields=["rule_rank"]),
        ]

    def __str__(self):
        return f"{self.location_of_the_referral} - {self.workflow_title} - {self.bonus_amount_eur_gross}"