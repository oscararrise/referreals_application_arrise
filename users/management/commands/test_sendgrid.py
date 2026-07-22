import os

from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class Command(BaseCommand):
    help = "Send a test email using SendGrid"

    def handle(self, *args, **options):
        load_dotenv()

        api_key = os.getenv("SENDGRID_API_KEY", "").strip()
        from_email = os.getenv("SENDGRID_FROM_EMAIL", "").strip()
        data_residency = "eu"
        to_email = "oscarbonilla70@gmail.com"
        self.stdout.write("========== SENDGRID CONFIG CHECK ==========")
        self.stdout.write(f"SENDGRID_API_KEY exists: {bool(api_key)}")
        self.stdout.write(f"SENDGRID_API_KEY starts with SG.: {api_key.startswith('SG.')}")
        self.stdout.write(f"SENDGRID_FROM_EMAIL: {from_email}")
        self.stdout.write(f"SENDGRID_DATA_RESIDENCY: {data_residency or '(empty)'}")
        self.stdout.write("===========================================")

        if not api_key:
            self.stderr.write(self.style.ERROR("SENDGRID_API_KEY is missing"))
            return

        if not api_key.startswith("SG."):
            self.stderr.write(self.style.ERROR("SENDGRID_API_KEY must start with SG."))
            return

        if not from_email:
            self.stderr.write(self.style.ERROR("SENDGRID_FROM_EMAIL is missing"))
            return

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject="SendGrid test email from Django",
            html_content="""
                <h2>SendGrid test</h2>
                <p>This email was sent successfully from Django using SendGrid.</p>
            """,
        )

        try:
            sg = SendGridAPIClient(api_key)

            response = sg.send(message)

            self.stdout.write(self.style.SUCCESS("Email sent to SendGrid."))
            self.stdout.write(f"Status Code: {response.status_code}")
            self.stdout.write(f"Body: {response.body}")
            self.stdout.write(f"Headers: {response.headers}")

            if response.status_code == 202:
                self.stdout.write(
                    self.style.SUCCESS(
                        "SendGrid accepted the email. Now check inbox/spam."
                    )
                )
            else:
                self.stderr.write(
                    self.style.WARNING(
                        f"SendGrid responded with status code {response.status_code}"
                    )
                )

        except Exception as e:
            self.stderr.write(self.style.ERROR("SendGrid failed."))
            self.stderr.write(f"Error type: {type(e)}")
            self.stderr.write(f"Error: {str(e)}")