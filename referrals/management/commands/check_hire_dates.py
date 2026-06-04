from django.core.management.base import BaseCommand
from referrals.models import JobviteApplication, EmployeeDirectoryHiBob


class Command(BaseCommand):
    help = "Check matches between Jobvite applications and HiBob employees"

    def handle(self, *args, **kwargs):
        total_apps = 0
        total_matches = 0
        with_hire_date = 0

        samples = []

        apps = JobviteApplication.objects.exclude(email__isnull=True)

        for app in apps:
            total_apps += 1

            hc = EmployeeDirectoryHiBob.objects.filter(
                email__iexact=app.email
            ).first()

            if hc:
                total_matches += 1

                if hc.start_date:
                    with_hire_date += 1

                if len(samples) < 10:
                    samples.append({
                        "email": app.email,
                        "name": f"{app.first_name} {app.last_name}",
                        "hire_date": hc.start_date
                    })

        self.stdout.write(self.style.SUCCESS("===== RESULTS ====="))
        self.stdout.write(f"Total Jobvite records: {total_apps}")
        self.stdout.write(f"Matches with HC: {total_matches}")
        self.stdout.write(f"With hire date: {with_hire_date}")

        self.stdout.write("\n===== SAMPLE DATA =====")
        for s in samples:
            self.stdout.write(str(s))