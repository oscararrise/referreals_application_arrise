url = "https://default214f6519cd194726a221b70378e889.f6.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/2494a02c71994dbf88ef4aa2c4055ef4/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=vGk4COhJzIhy0RzxNkWd-I0a1OGyHbr7wi9st41qmkw"
import os
import requests
from django.conf import settings


def send_referral_email_via_power_automate(
    candidate_name,
    candidate_email,
    role_name,
    referral_link,
    general_referral_link,
    employee_id,
    sender_email,
    employee_name,
):
    payload = {
    "candidate_name": candidate_name,
    "candidate_email": candidate_email,
    "role_name": role_name,
    "referral_link": referral_link,
    "general_referral_link": general_referral_link,
    "employee_id": employee_id,
    "sender_email": sender_email,
    "employee_name": employee_name,
}

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    if response.content:
        return response.json()

    return {}