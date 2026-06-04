from datetime import datetime, timedelta

import csv

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render

from redshift_client import build_referral_link_by_role

from .forms import ReferralForm
from .models import (
    EmployeeDirectoryHiBob,
    JobviteApplication,
    JobviteRequisitionReferralDetail,
    ReferralBonusRule,
)
from .power_automate_services import send_referral_email_via_power_automate
from .utils import generate_qr_base64


ADMIN_REFERRAL_COLUMNS = [
    "Referrer HiBob ID",
    "Referrer full name",
    "Referrer email",
    "Referrer termination date",
    "Referrer site",
    "Referrer department",
    "Referrer Sub department",
    "Referrer is TA?",
    "Referrer is Hiring manager?",
    "Referrer is interviewer?",
    "Hired referral terminated before 3 months?",
    "Referrer is self?",
    "Referrer entity",
    "Referrer eligibility",
    "Referral bonus region",
    "Total referral bonus amount (EUR gross)",
    "3 weeks from start",
    "Referral payment date",
    "Special campaign 2nd installment",
    "Special campaign 3rd installment",
    "Requisition Country",
    "Entity",
    "Workflow Title",
    "Table language",
    "Presenter / shuffler",
    "Full time / part time",
    "Candidate name",
    "Hire termination date",
    "Start date",
    "Month of payment",
    "Candidate HiBob ID",
    "3 months from start",
    "Candidate Email",
    "Req ID",
    "Job title",
    "Application date",
    "Source",
    "Recruiter",
    "Sub department",
    "Is relocation required?",
]


def _parse_hire_date(value):
    if not value:
        return None

    value = str(value).strip()

    if not value or value == "--":
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d-%b-%Y",
        "%d %b %Y",
        "%b %d, %Y",
    ]

    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    return None


def _format_date(value):
    if not value:
        return "--"

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    parsed_date = _parse_hire_date(value)

    if parsed_date:
        return parsed_date.strftime("%Y-%m-%d")

    return str(value)


def _format_month_year(value):
    parsed_date = _parse_hire_date(value)

    if not parsed_date:
        return ""

    return parsed_date.strftime("%b-%y")


def _add_days_to_date(value, days):
    parsed_date = _parse_hire_date(value)

    if not parsed_date:
        return "--"

    return (parsed_date + timedelta(days=days)).strftime("%Y-%m-%d")


def _get_month_of_payment(value):
    parsed_date = _parse_hire_date(value)

    if not parsed_date:
        return "--"

    return parsed_date.strftime("%B %Y")


def _clean_value(value):
    if value is None or value == "":
        return "--"

    return value


def _build_full_name(first_name, last_name):
    full_name = f"{first_name or ''} {last_name or ''}".strip()
    return full_name if full_name else "--"


def _normalize_name(value):
    if not value:
        return ""

    return " ".join(str(value).strip().lower().split())


def _normalize_rule_value(value):
    if value is None:
        return ""

    return " ".join(str(value).strip().lower().split())


def _optional_rule_match(rule_value, referral_value):
    rule_value = _normalize_rule_value(rule_value)
    referral_value = _normalize_rule_value(referral_value)

    return not rule_value or rule_value == referral_value


def _is_closed_status(workflow_state):
    if not workflow_state:
        return False

    status = workflow_state.lower()

    return (
        "rejected" in status
        or "withdrew" in status
        or "rescinded" in status
        or "video rejected" in status
    )


def _get_display_workflow_state(workflow_state, is_admin=False):
    if not workflow_state:
        return "--"

    if is_admin:
        return workflow_state

    closed_states = {
        "rejected",
        "candidate withdrew",
        "offer rejected",
        "offer rescinded",
        "video rejected",
    }

    normalized_state = " ".join(str(workflow_state).strip().lower().split())

    if normalized_state in closed_states:
        return "Application closed"

    return workflow_state


def _is_hired_status(workflow_state):
    if not workflow_state:
        return False

    return "hired" in workflow_state.lower()


def _is_ta_employee(employee):
    if not employee or not employee.sub_department:
        return "No"

    ta_sub_departments = {
        "Global TA",
        "Talent Acquisition",
        "Live Casino TA",
    }

    return "Yes" if employee.sub_department.strip() in ta_sub_departments else "No"


def _is_self_referral(referrer_employee, candidate_employee):
    if not referrer_employee or not candidate_employee:
        return "--"

    if not referrer_employee.email or not candidate_employee.email:
        return "--"

    referrer_email = referrer_employee.email.lower().strip()
    candidate_email = candidate_employee.email.lower().strip()

    return "Yes" if referrer_email == candidate_email else "No"


def _hired_referral_terminated_before_3_months(referral):
    candidate_employee = getattr(referral, "candidate_employee", None)

    if not candidate_employee:
        return "--"

    parsed_start_date = _parse_hire_date(candidate_employee.start_date)
    parsed_termination_date = _parse_hire_date(candidate_employee.termination_date)

    if not parsed_start_date or not parsed_termination_date:
        return "--"

    days_worked = (parsed_termination_date - parsed_start_date).days

    return "Yes" if days_worked < 90 else "No"


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from _iter_dicts(child)

    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _get_custom_field_value(referral, field_code=None, key=None):
    if not referral or not referral.raw_payload:
        return ""

    expected_field_code = str(field_code or "").strip().lower()
    expected_key = str(key or "").strip().lower()

    for item in _iter_dicts(referral.raw_payload):
        current_field_code = str(item.get("fieldCode") or "").strip().lower()
        current_key = str(item.get("key") or "").strip().lower()

        field_code_match = expected_field_code and current_field_code == expected_field_code
        key_match = expected_key and current_key == expected_key

        if field_code_match or key_match:
            value = item.get("value")
            return str(value or "").strip()

    return ""


def _build_requisition_details_map(referrals):
    req_ids = {
        str(referral.requisition_id).strip()
        for referral in referrals
        if referral.requisition_id
    }

    details_map = {}

    if not req_ids:
        return details_map

    details = JobviteRequisitionReferralDetail.objects.filter(req_id__in=req_ids)

    for detail in details:
        req_id = str(detail.req_id).strip()

        if req_id not in details_map:
            details_map[req_id] = {
                "workflow_title": "",
                "recruiters": set(),
                "hiring_managers": set(),
                "interviewers": set(),
            }

        if detail.workflow_title and not details_map[req_id]["workflow_title"]:
            details_map[req_id]["workflow_title"] = detail.workflow_title.strip()

        recruiter_name = _normalize_name(detail.recruiter_name)
        hiring_manager_name = _normalize_name(detail.hiring_manager_name)
        interviewer_name = _normalize_name(detail.interviewer_full_name)

        if recruiter_name:
            details_map[req_id]["recruiters"].add(recruiter_name)

        if hiring_manager_name:
            details_map[req_id]["hiring_managers"].add(hiring_manager_name)

        if interviewer_name:
            details_map[req_id]["interviewers"].add(interviewer_name)

    return details_map


def _get_workflow_title_from_details(referral, requisition_details_map):
    if not referral or not referral.requisition_id:
        return "--"

    req_id = str(referral.requisition_id).strip()
    details = requisition_details_map.get(req_id)

    if not details:
        return "--"

    workflow_title = details.get("workflow_title")

    if not workflow_title:
        return "--"

    return workflow_title


def _get_recruiter_from_details(referral, requisition_details_map):
    if not referral or not referral.requisition_id:
        return "--"

    req_id = str(referral.requisition_id).strip()
    details = requisition_details_map.get(req_id)

    if not details:
        return "--"

    recruiters = details.get("recruiters") or set()

    if not recruiters:
        return "--"

    formatted_recruiters = sorted({
        " ".join(recruiter.title().split())
        for recruiter in recruiters
        if recruiter
    })

    return ", ".join(formatted_recruiters) if formatted_recruiters else "--"


def _get_workflow_title_for_bonus(referral, requisition_details_map):
    workflow_title = _get_workflow_title_from_details(
        referral,
        requisition_details_map,
    )

    return "" if workflow_title == "--" else workflow_title


def _get_presenter_shuffler(referral):
    value = _get_custom_field_value(
        referral,
        field_code="dealer__shuffler",
        key="Dealer / shuffler",
    )

    if value:
        return value

    job_title = str(referral.job_title or "").lower()

    if "shuffler" in job_title:
        return "Shuffler"

    if "presenter" in job_title:
        return "Presenter"

    return ""


def _get_table_language(referral, workflow_title=None):
    allowed_workflows = {
        "presenter / shuffler",
        "presenter / shuffler - video first",
    }

    if workflow_title:
        normalized_workflow = str(workflow_title).strip().lower()

        if normalized_workflow not in allowed_workflows:
            return ""

    value = _get_custom_field_value(
        referral,
        field_code="table_language",
        key="Table language",
    )

    return value or ""


def _get_sub_department_for_bonus(referral):
    value = _get_custom_field_value(
        referral,
        field_code="sub_department",
        key="Sub department",
    )

    if value:
        return value

    return referral.department or ""


def _get_entity_from_job(referral):
    value = _get_custom_field_value(
        referral,
        field_code="entity",
        key="Entity",
    )

    return value or ""


def _get_is_relocation_required(referral):
    if not referral or not referral.raw_payload:
        return "--"

    for item in _iter_dicts(referral.raw_payload):
        field_code = str(item.get("fieldCode") or "").strip().lower()
        key = str(item.get("key") or "").strip().lower()

        if "relocation" not in field_code and "relocation" not in key:
            continue

        value = item.get("value")

        if value is None or str(value).strip() == "":
            return "--"

        value = str(value).strip()
        normalized_value = value.lower()

        if normalized_value in {"yes", "true", "1", "required"}:
            return "Yes"

        if normalized_value in {"no", "false", "0", "not required"}:
            return "No"

        return value

    return "--"


def _is_referrer_hiring_manager(referral, referrer_employee, requisition_details_map):
    if not referral or not referrer_employee or not referral.requisition_id:
        return "No"

    req_id = str(referral.requisition_id).strip()

    referrer_name = _normalize_name(
        _build_full_name(
            referrer_employee.first_name,
            referrer_employee.last_name,
        )
    )

    if not referrer_name:
        return "No"

    details = requisition_details_map.get(req_id)

    if not details:
        return "No"

    return "Yes" if referrer_name in details["hiring_managers"] else "No"


def _is_referrer_interviewer(referral, referrer_employee, requisition_details_map):
    if not referral or not referrer_employee or not referral.requisition_id:
        return "No"

    req_id = str(referral.requisition_id).strip()

    referrer_name = _normalize_name(
        _build_full_name(
            referrer_employee.first_name,
            referrer_employee.last_name,
        )
    )

    if not referrer_name:
        return "No"

    details = requisition_details_map.get(req_id)

    if not details:
        return "No"

    return "Yes" if referrer_name in details["interviewers"] else "No"


def _get_referrer_eligibility(
    referral,
    referrer_employee,
    candidate_employee,
    requisition_details_map,
):
    if not referral.hibob_id:
        return "Source match not found"

    if not referrer_employee:
        return "Source match not found"

    is_interviewer = _is_referrer_interviewer(
        referral,
        referrer_employee,
        requisition_details_map,
    )

    is_hiring_manager = _is_referrer_hiring_manager(
        referral,
        referrer_employee,
        requisition_details_map,
    )

    is_ta = _is_ta_employee(referrer_employee)
    is_self = _is_self_referral(referrer_employee, candidate_employee)
    terminated_before_3_months = _hired_referral_terminated_before_3_months(referral)

    candidate_start_date = (
        candidate_employee.start_date
        if candidate_employee
        else None
    )

    three_months_from_start = _parse_hire_date(
        _add_days_to_date(candidate_start_date, 90)
    )

    referrer_termination_date = _parse_hire_date(referrer_employee.termination_date)

    referrer_termination_condition = False

    if not referrer_termination_date:
        referrer_termination_condition = True
    elif three_months_from_start:
        referrer_termination_condition = referrer_termination_date < three_months_from_start

    if (
        is_interviewer == "No"
        and is_hiring_manager == "No"
        and is_ta == "No"
        and is_self == "No"
        and referrer_termination_condition
        and terminated_before_3_months == "Yes"
    ):
        return "Eligible for bonus"

    return "Not eligible"


def _get_matching_bonus_rule(
    referral,
    referrer_employee,
    candidate_employee,
    requisition_details_map,
):
    eligibility = _get_referrer_eligibility(
        referral,
        referrer_employee,
        candidate_employee,
        requisition_details_map,
    )

    if eligibility != "Eligible for bonus":
        return None

    referral_bonus_region = (
        referrer_employee.site_country.strip()
        if referrer_employee and referrer_employee.site_country
        else ""
    )

    workflow_title = _get_workflow_title_for_bonus(
        referral,
        requisition_details_map,
    )

    application_date = referral.sent_date.date() if referral.sent_date else None

    if not referral_bonus_region or not workflow_title or not application_date:
        return None

    sub_department = _get_sub_department_for_bonus(referral)
    presenter_shuffler = _get_presenter_shuffler(referral)
    table_language = _get_table_language(referral, workflow_title)

    full_time_part_time = (
        candidate_employee.employment_type.strip()
        if candidate_employee and candidate_employee.employment_type
        else ""
    )

    candidate_rules = ReferralBonusRule.objects.filter(
        location_of_the_referral__iexact=referral_bonus_region,
        workflow_title__iexact=workflow_title,
        date_effective__lte=application_date,
    ).filter(
        Q(date_end__isnull=True) | Q(date_end__gte=application_date)
    )

    matched_rules = []

    for rule in candidate_rules:
        if not _optional_rule_match(rule.sub_department, sub_department):
            continue

        if not _optional_rule_match(rule.presenter_shuffler, presenter_shuffler):
            continue

        if not _optional_rule_match(rule.table_language, table_language):
            continue

        if not _optional_rule_match(rule.full_time_part_time, full_time_part_time):
            continue

        matched_rules.append(rule)

    if not matched_rules:
        return None

    return max(
        matched_rules,
        key=lambda rule: rule.rule_rank or 0,
    )


def _get_total_referral_bonus_amount_gross(
    referral,
    referrer_employee,
    candidate_employee,
    requisition_details_map,
):
    rule = _get_matching_bonus_rule(
        referral,
        referrer_employee,
        candidate_employee,
        requisition_details_map,
    )

    if not rule or rule.bonus_amount_eur_gross is None:
        return ""

    return rule.bonus_amount_eur_gross


def _get_base_referrals_queryset(user):
    if user.role == "admin":
        return JobviteApplication.objects.filter(source__icontains="HiBobID")

    employee = EmployeeDirectoryHiBob.objects.filter(
        email=user.email.lower()
    ).first()

    if not employee:
        return JobviteApplication.objects.none()

    return JobviteApplication.objects.filter(
        source__icontains=str(employee.employee_id)
    )


def _attach_employee_data_to_referrals(referral_list, is_admin=False):
    referrer_hibob_ids = list({
        str(referral.hibob_id).strip()
        for referral in referral_list
        if referral.hibob_id
    })

    candidate_emails = list({
        referral.email.strip().lower()
        for referral in referral_list
        if referral.email
    })

    employee_by_id = {}
    employee_by_email = {}

    chunk_size = 800

    for i in range(0, len(referrer_hibob_ids), chunk_size):
        id_chunk = referrer_hibob_ids[i:i + chunk_size]

        employees = EmployeeDirectoryHiBob.objects.filter(
            employee_id__in=id_chunk
        )

        for employee in employees:
            employee_by_id[str(employee.employee_id).strip()] = employee

    for i in range(0, len(candidate_emails), chunk_size):
        email_chunk = candidate_emails[i:i + chunk_size]

        employees = EmployeeDirectoryHiBob.objects.filter(
            email__in=email_chunk
        )

        for employee in employees:
            employee_by_email[employee.email.strip().lower()] = employee
        for referral in referral_list:
            referrer_id = str(referral.hibob_id).strip() if referral.hibob_id else None
            candidate_email = referral.email.strip().lower() if referral.email else None
        
            referral.referrer_employee = employee_by_id.get(referrer_id)
            referral.candidate_employee = employee_by_email.get(candidate_email)
        
            referral.hire_date = (
                referral.candidate_employee.start_date
                if referral.candidate_employee
                else None
            )
        
            referral.display_workflow_state = _get_display_workflow_state(
                referral.workflow_state,
                is_admin=is_admin,
            )
        
            referral.user_payment_date = "--"
        
            if not is_admin and _is_hired_status(referral.workflow_state):
                referral.user_payment_date = _add_days_to_date(referral.hire_date, 90)

    return referral_list


def _build_referral_list(user, country=None, city=None, role_name=None, status=None):
    referrals = _get_base_referrals_queryset(user)

    if country:
        referrals = referrals.filter(location__icontains=country)

    if city:
        referrals = referrals.filter(location__icontains=city)

    if role_name:
        referrals = referrals.filter(job_title__icontains=role_name)

    if status:
        referrals = referrals.filter(workflow_state__icontains=status)

    referrals = referrals.order_by("-last_updated_date")

    referral_list = list(referrals)

    return _attach_employee_data_to_referrals(
        referral_list,
        is_admin=user.role == "admin",
    )


def _build_admin_referral_rows(referrals):
    rows = []
    requisition_details_map = _build_requisition_details_map(referrals)

    for referral in referrals:
        referrer_employee = getattr(referral, "referrer_employee", None)
        candidate_employee = getattr(referral, "candidate_employee", None)

        workflow_title = _get_workflow_title_from_details(
            referral,
            requisition_details_map,
        )

        workflow_title_for_bonus = "" if workflow_title == "--" else workflow_title

        candidate_start_date = (
            candidate_employee.start_date
            if candidate_employee
            else None
        )

        candidate_termination_date = (
            candidate_employee.termination_date
            if candidate_employee
            else None
        )

        table_language = _get_table_language(referral, workflow_title_for_bonus)
        presenter_shuffler = _get_presenter_shuffler(referral)
        sub_department = _get_sub_department_for_bonus(referral)
        relocation_required = _get_is_relocation_required(referral)

        row = [
            _clean_value(referral.hibob_id),
            _build_full_name(
                referrer_employee.first_name if referrer_employee else None,
                referrer_employee.last_name if referrer_employee else None,
            ),
            _clean_value(referrer_employee.email if referrer_employee else None),
            _format_date(referrer_employee.termination_date if referrer_employee else None),
            _clean_value(referrer_employee.site if referrer_employee else None),
            _clean_value(referrer_employee.department if referrer_employee else None),
            _clean_value(referrer_employee.sub_department if referrer_employee else None),
            _is_ta_employee(referrer_employee),
            _is_referrer_hiring_manager(
                referral,
                referrer_employee,
                requisition_details_map,
            ),
            _is_referrer_interviewer(
                referral,
                referrer_employee,
                requisition_details_map,
            ),
            _hired_referral_terminated_before_3_months(referral),
            _is_self_referral(referrer_employee, candidate_employee),
            _clean_value(referrer_employee.entity if referrer_employee else None),
            _get_referrer_eligibility(
                referral,
                referrer_employee,
                candidate_employee,
                requisition_details_map,
            ),
            _clean_value(referrer_employee.site_country if referrer_employee else None),
            _get_total_referral_bonus_amount_gross(
                referral,
                referrer_employee,
                candidate_employee,
                requisition_details_map,
            ),
            _add_days_to_date(candidate_start_date, 21),
            "--",
            "--",
            "--",
            _clean_value(referral.location),
            _clean_value(_get_entity_from_job(referral)),
            workflow_title,
            _clean_value(table_language),
            _clean_value(presenter_shuffler),
            _clean_value(candidate_employee.employment_type if candidate_employee else None),
            _build_full_name(referral.first_name, referral.last_name),
            _format_date(candidate_termination_date),
            _format_date(candidate_start_date),
            _get_month_of_payment(candidate_start_date),
            _clean_value(candidate_employee.employee_id if candidate_employee else None),
            _add_days_to_date(candidate_start_date, 90),
            _clean_value(referral.email),
            _clean_value(referral.requisition_id),
            _clean_value(referral.job_title),
            _format_date(referral.sent_date),
            _clean_value(referral.source),
            _get_recruiter_from_details(referral, requisition_details_map),
            _clean_value(sub_department),
            _clean_value(relocation_required),
        ]

        rows.append(row)

    return rows


def _build_admin_dashboard_stats(referrals):
    requisition_details_map = _build_requisition_details_map(referrals)

    total_referrals = len(referrals)
    hired = 0
    rejected = 0
    candidate_withdrew = 0
    in_progress = 0
    eligible_for_bonus = 0
    total_bonus_amount = 0.0
    hire_days = []
    unique_referrers = set()

    for referral in referrals:
        workflow_state = referral.workflow_state or ""
        normalized_workflow_state = " ".join(
            str(workflow_state).strip().lower().split()
        )

        if normalized_workflow_state == "candidate withdrew":
            candidate_withdrew += 1

        if _is_hired_status(workflow_state):
            hired += 1
        elif _is_closed_status(workflow_state):
            rejected += 1
        else:
            in_progress += 1

        referrer_employee = getattr(referral, "referrer_employee", None)
        candidate_employee = getattr(referral, "candidate_employee", None)

        if _get_referrer_eligibility(
            referral,
            referrer_employee,
            candidate_employee,
            requisition_details_map,
        ) == "Eligible for bonus":
            eligible_for_bonus += 1

        bonus_amount = _get_total_referral_bonus_amount_gross(
            referral,
            referrer_employee,
            candidate_employee,
            requisition_details_map,
        )

        try:
            total_bonus_amount += float(bonus_amount or 0)
        except (TypeError, ValueError):
            pass

        sent_date = referral.sent_date.date() if referral.sent_date else None
        hire_date_value = getattr(referral, "hire_date", None)
        parsed_hire_date = _parse_hire_date(hire_date_value)

        if sent_date and parsed_hire_date:
            days_to_hire = (parsed_hire_date - sent_date).days
            if days_to_hire >= 0:
                hire_days.append(days_to_hire)

        if referrer_employee and referrer_employee.employee_id:
            unique_referrers.add(str(referrer_employee.employee_id).strip())
        elif referral.hibob_id:
            unique_referrers.add(str(referral.hibob_id).strip())

    avg_days_to_hire = int(sum(hire_days) / len(hire_days)) if hire_days else 0

    return {
        "total_referrals": total_referrals,
        "hired": hired,
        "rejected": rejected,
        "candidate_withdrew": candidate_withdrew,
        "in_progress": in_progress,
        "eligible_for_bonus": eligible_for_bonus,
        "avg_days_to_hire": avg_days_to_hire,
        "total_bonus_amount": f"{total_bonus_amount:.2f}".rstrip("0").rstrip("."),
        "unique_referrers": len(unique_referrers),
    } 


def _build_admin_chart_data(referrals):
    requisition_details_map = _build_requisition_details_map(referrals)

    status_counts = {
        "Hired": 0,
        "Rejected": 0,
        "In progress": 0,
        "Other": 0,
    }

    region_counts = {}

    eligibility_counts = {
        "Eligible for bonus": 0,
        "Not eligible": 0,
        "Source match not found": 0,
    }

    bonus_by_region = {}

    for referral in referrals:
        workflow_state = referral.workflow_state or ""

        if _is_hired_status(workflow_state):
            status_counts["Hired"] += 1
        elif _is_closed_status(workflow_state):
            status_counts["Rejected"] += 1
        elif workflow_state:
            status_counts["In progress"] += 1
        else:
            status_counts["Other"] += 1

        referrer_employee = getattr(referral, "referrer_employee", None)
        candidate_employee = getattr(referral, "candidate_employee", None)

        region = _clean_value(
            getattr(
                referrer_employee,
                "site_country",
                None,
            )
        )

        if region and region != "--":
            region_counts[region] = region_counts.get(region, 0) + 1

            if region not in bonus_by_region:
                bonus_by_region[region] = 0

        eligibility = _get_referrer_eligibility(
            referral,
            referrer_employee,
            candidate_employee,
            requisition_details_map,
        )

        if eligibility not in eligibility_counts:
            eligibility_counts[eligibility] = 0

        eligibility_counts[eligibility] += 1

        bonus_amount = _get_total_referral_bonus_amount_gross(
            referral,
            referrer_employee,
            candidate_employee,
            requisition_details_map,
        )

        try:
            numeric_bonus = float(bonus_amount or 0)
        except (TypeError, ValueError):
            numeric_bonus = 0

        if region and region != "--":
            bonus_by_region[region] = bonus_by_region.get(region, 0) + numeric_bonus

    total_status = sum(status_counts.values()) or 1

    status_distribution = [
        {
            "label": label,
            "count": count,
            "percent": int((count * 100) / total_status),
        }
        for label, count in status_counts.items()
        if count > 0
    ]

    sorted_regions = sorted(
        region_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    total_region = sum(region_counts.values()) or 1

    region_distribution = [
        {
            "label": region,
            "count": count,
            "percent": int((count * 100) / total_region),
        }
        for region, count in sorted_regions
    ]

    total_eligibility = sum(eligibility_counts.values()) or 1

    eligibility_distribution = [
        {
            "label": label,
            "count": count,
            "percent": int((count * 100) / total_eligibility),
        }
        for label, count in eligibility_counts.items()
        if count > 0
    ]

    sorted_bonus_regions = sorted(
        bonus_by_region.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    total_bonus = sum(bonus_by_region.values())

    bonus_by_region_distribution = [
        {
            "label": region,
            "amount": f"{amount:.2f}".rstrip("0").rstrip("."),
            "percent": int((amount * 100) / total_bonus) if total_bonus > 0 else 0,
        }
        for region, amount in sorted_bonus_regions
    ]

    return {
        "status_distribution": status_distribution,
        "region_distribution": region_distribution,
        "eligibility_distribution": eligibility_distribution,
        "bonus_by_region_distribution": bonus_by_region_distribution,
    }


def _export_referrals_to_csv(referrals, is_admin):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="referrals_export.csv"'
    writer = csv.writer(response)

    if is_admin:
        writer.writerow(ADMIN_REFERRAL_COLUMNS)
        rows = _build_admin_referral_rows(referrals)

        for row in rows:
            writer.writerow([str(value) for value in row])

    else:
        writer.writerow([
            "First Name",
            "Last Name",
            "Email",
            "Status",
            "Role",
            "Referred Date",
        ])

        for referral in referrals:
            writer.writerow([
                referral.first_name,
                referral.last_name,
                referral.email,
                getattr(referral, "display_workflow_state", "--"),
                referral.job_title,
                _format_date(referral.sent_date),
            ])

    return response


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect("/")

        messages.error(request, "Invalid email or password")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("/login/")


@login_required
def create_referral(request):
    generated_link = None
    generated_qr = None
    form = ReferralForm()

    if request.method == "POST":
        action = request.POST.get("action")
        form = ReferralForm(request.POST)

        if form.is_valid():
            candidate_name = form.cleaned_data["candidate_name"]
            candidate_email = form.cleaned_data["candidate_email"]
            role_name = form.cleaned_data["role_name"]

            employee = EmployeeDirectoryHiBob.objects.filter(
                email=request.user.email.lower()
            ).first()

            if not employee:
                messages.error(request, "Employee ID not found for this user")
            else:
                result = build_referral_link_by_role(role_name, employee.employee_id)

                if not result:
                    messages.error(request, "Role not found")
                else:
                    generated_link = result["link"]
                    generated_qr = generate_qr_base64(generated_link)
                    general_referral_link = (
                                                "https://jobs.jobvite.com/careers/pragmaticplay/jobs"
                                                f"?__jvst=Referral&__jvsd=HiBobID_{employee.employee_id}"
                                            )
                    if action == "generate_link":
                        messages.success(request, "Referral link generated successfully")

                    elif action == "send_email":
                        try:
                            send_referral_email_via_power_automate(
                                                                      candidate_name=candidate_name,
                                                                      candidate_email=candidate_email,
                                                                      role_name=role_name,
                                                                      referral_link=generated_link,
                                                                      general_referral_link=general_referral_link,
                                                                      employee_id=employee.employee_id,
                                                                      sender_email=request.user.email,
                                                                      employee_name=employee.first_name,
                                                                  )
                            messages.success(request, "Referral email sent successfully")
                        except Exception as error:
                            messages.error(request, f"Error sending email: {error}")
        else:
            messages.error(request, "Please correct the form errors")

    return render(
        request,
        "referrals/create_referral.html",
        {
            "form": form,
            "generated_link": generated_link,
            "generated_qr": generated_qr,
        },
    )


@login_required
def my_referrals(request):
    is_admin = request.user.role == "admin"

    filters = {
        "status": request.GET.get("status", "").strip(),
        "country": request.GET.get("country", "").strip(),
        "city": request.GET.get("city", "").strip(),
        "role_name": request.GET.get("role_name", "").strip(),
        "is_ta": request.GET.get("is_ta", "").strip(),
        "is_hiring_manager": request.GET.get("is_hiring_manager", "").strip(),
        "is_interviewer": request.GET.get("is_interviewer", "").strip(),
        "terminated_before_3_months": request.GET.get(
            "terminated_before_3_months",
            "",
        ).strip(),
        "is_self_referral": request.GET.get("is_self_referral", "").strip(),
        "referrer_eligibility": request.GET.get("referrer_eligibility", "").strip(),
        "referral_bonus_region": request.GET.get("referral_bonus_region", "").strip(),
        "is_relocation_required": request.GET.get("is_relocation_required", "").strip(),
    }

    referral_list = _build_referral_list(
        request.user,
        country=filters["country"],
        city=filters["city"],
        role_name=filters["role_name"],
        status=filters["status"],
    )

    if is_admin and filters["is_ta"]:
        referral_list = [
            referral for referral in referral_list
            if _is_ta_employee(
                getattr(referral, "referrer_employee", None)
            ) == filters["is_ta"]
        ]

    if is_admin and (filters["is_hiring_manager"] or filters["is_interviewer"]):
        requisition_details_map = _build_requisition_details_map(referral_list)

        if filters["is_hiring_manager"]:
            referral_list = [
                referral for referral in referral_list
                if _is_referrer_hiring_manager(
                    referral,
                    getattr(referral, "referrer_employee", None),
                    requisition_details_map,
                ) == filters["is_hiring_manager"]
            ]

        if filters["is_interviewer"]:
            referral_list = [
                referral for referral in referral_list
                if _is_referrer_interviewer(
                    referral,
                    getattr(referral, "referrer_employee", None),
                    requisition_details_map,
                ) == filters["is_interviewer"]
            ]

    if is_admin and filters["terminated_before_3_months"]:
        referral_list = [
            referral for referral in referral_list
            if _hired_referral_terminated_before_3_months(referral)
            == filters["terminated_before_3_months"]
        ]

    if is_admin and filters["is_self_referral"]:
        referral_list = [
            referral for referral in referral_list
            if _is_self_referral(
                getattr(referral, "referrer_employee", None),
                getattr(referral, "candidate_employee", None),
            ) == filters["is_self_referral"]
        ]

    if is_admin and filters["referrer_eligibility"]:
        requisition_details_map = _build_requisition_details_map(referral_list)

        referral_list = [
            referral for referral in referral_list
            if _get_referrer_eligibility(
                referral,
                getattr(referral, "referrer_employee", None),
                getattr(referral, "candidate_employee", None),
                requisition_details_map,
            ) == filters["referrer_eligibility"]
        ]

    if is_admin and filters["referral_bonus_region"]:
        referral_list = [
            referral for referral in referral_list
            if _clean_value(
                getattr(
                    getattr(referral, "referrer_employee", None),
                    "site_country",
                    None,
                )
            ) == filters["referral_bonus_region"]
        ]

    if is_admin and filters["is_relocation_required"]:
        referral_list = [
            referral for referral in referral_list
            if _get_is_relocation_required(referral) == filters["is_relocation_required"]
        ]

    referral_bonus_regions = sorted({
        getattr(referral.referrer_employee, "site_country", "")
        for referral in referral_list
        if getattr(referral, "referrer_employee", None)
        and getattr(referral.referrer_employee, "site_country", None)
    })

    if request.GET.get("export") == "csv":
        return _export_referrals_to_csv(referral_list, is_admin)

    paginator = Paginator(referral_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    admin_columns = []
    admin_rows = []
    admin_dashboard = None
    chart_data = None

    if is_admin:
        admin_columns = ADMIN_REFERRAL_COLUMNS
        admin_rows = _build_admin_referral_rows(page_obj)
        admin_dashboard = _build_admin_dashboard_stats(referral_list)
        chart_data = _build_admin_chart_data(referral_list)

    return render(
        request,
        "referrals/my_referrals.html",
        {
            "referrals": page_obj,
            "page_obj": page_obj,
            "page_title": "All Referrals" if is_admin else "My Referrals",
            "is_admin": is_admin,
            "filters": filters,
            "admin_columns": admin_columns,
            "admin_rows": admin_rows,
            "admin_dashboard": admin_dashboard,
            "chart_data": chart_data,
            "referral_bonus_regions": referral_bonus_regions,
        },
    )


@login_required
def home(request):
    is_admin = request.user.role == "admin"

    employee = EmployeeDirectoryHiBob.objects.filter(
        email=request.user.email.lower()
    ).first()

    general_referral_link = ""

    if employee and employee.employee_id:
        general_referral_link = (
            "https://jobs.jobvite.com/careers/pragmaticplay/jobs"
            f"?__jvst=Referral&__jvsd=HiBobID_{employee.employee_id}"
        )

    bonus_campaign_message = "Refer and earn rewards"
    bonus_campaign_country = ""
    max_bonus_amount = ""

    if employee and employee.site_country:
        bonus_campaign_country = employee.site_country.strip()
        today = datetime.today().date()

        max_bonus = ReferralBonusRule.objects.filter(
    location_of_the_referral__iexact=bonus_campaign_country,
    date_effective__lte=today,
    date_end__isnull=True,
                        ).exclude(
                            bonus_amount_eur_net__isnull=True
                        ).aggregate(
                            max_bonus=Max("bonus_amount_eur_net")
                        )["max_bonus"]

        max_bonus_amount = _format_bonus_amount(max_bonus)

        if max_bonus_amount:
            bonus_campaign_message = f"Refer and earn up to {max_bonus_amount} EUR"

    referral_list = _build_referral_list(request.user)

    total_referrals = len(referral_list)

    successfully_hired = sum(
        1 for referral in referral_list
        if _is_hired_status(referral.workflow_state)
    )

    rejected = sum(
        1 for referral in referral_list
        if _is_closed_status(referral.workflow_state)
    )

    in_progress = sum(
        1 for referral in referral_list
        if referral.workflow_state
        and not _is_hired_status(referral.workflow_state)
        and not _is_closed_status(referral.workflow_state)
    )

    eligible_for_bonus = sum(
        1 for referral in referral_list
        if getattr(referral, "hire_date", None)
        and _is_hired_status(referral.workflow_state)
    )

    hired_days = []

    for referral in referral_list:
        if not referral.sent_date:
            continue

        if not getattr(referral, "hire_date", None):
            continue

        hire_date = _parse_hire_date(referral.hire_date)

        if not hire_date:
            continue

        sent_date = referral.sent_date.date()
        diff = (hire_date - sent_date).days

        if diff >= 0:
            hired_days.append(diff)

    avg_days_to_hire = int(sum(hired_days) / len(hired_days)) if hired_days else 0

    context = {
        "total_referrals": total_referrals,
        "in_progress": in_progress,
        "successfully_hired": successfully_hired,
        "eligible_for_bonus": eligible_for_bonus,
        "rejected": rejected,
        "avg_days_to_hire": avg_days_to_hire,
        "leaderboard": [],
        "is_admin": is_admin,
        "general_referral_link": general_referral_link,
        "bonus_campaign_message": bonus_campaign_message,
        "bonus_campaign_country": bonus_campaign_country,
        "max_bonus_amount": max_bonus_amount,
    }

    return render(request, "referrals/home.html", context)

def _format_bonus_amount(value):
    if value is None or value == "":
        return ""

    try:
        amount = float(value)
    except (TypeError, ValueError):
        return ""

    if amount.is_integer():
        return str(int(amount))

    return f"{amount:.2f}".rstrip("0").rstrip(".")