import os

import requests
from dotenv import load_dotenv

load_dotenv()


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
    url = os.getenv("POWER_AUTOMATE_REFERRAL_EMAIL_URL")

    if not url:
        raise ValueError("POWER_AUTOMATE_REFERRAL_EMAIL_URL is missing in .env")

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