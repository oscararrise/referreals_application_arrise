import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send_otp_email(to_email: str, otp_code: str) -> bool:
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('SENDGRID_FROM_EMAIL')
    data_residency = os.getenv('SENDGRID_DATA_RESIDENCY', '').lower()

    if not sendgrid_api_key:
        raise ValueError('SENDGRID_API_KEY is not configured.')

    if not from_email:
        raise ValueError('SENDGRID_FROM_EMAIL is not configured.')

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject='ARRISE Referral Platform - Verification code',
        html_content=f"""
    <div style="font-family: Arial, sans-serif; color: #111827;">
        <h2>ARRISE Referral Platform</h2>
        <p>Hi, this is your OTP verification code:</p>
        <h1 style="letter-spacing: 4px;">{otp_code}</h1>
        <p>This code is valid for 5 minutes.</p>
        <p>If you did not request this code, you can ignore this email.</p>
    </div>
"""
    )

    sg = SendGridAPIClient(sendgrid_api_key)

    if data_residency == 'eu':
        sg.set_sendgrid_data_residency('eu')

    response = sg.send(message)

    return 200 <= response.status_code < 300