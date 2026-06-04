import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from referrals.models import EmployeeDirectoryHiBob
from tqdm import tqdm


class Command(BaseCommand):
    help = "Sync HiBob employee directory from CSV file"

    def handle(self, *args, **kwargs):
        base_dir = Path.cwd()
        csv_path = base_dir / "files" / "HCreport.csv"

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        with open(csv_path, mode="r", encoding="latin-1", newline="") as file:
            rows = list(csv.DictReader(file))

        def parse(row):
            return {
                "email": (row.get("Email") or "").strip().lower(),
                "employee_id": (row.get("Employee ID") or "").strip(),
                "first_name": (row.get("First name") or "").strip(),
                "last_name": (row.get("Last name") or "").strip(),
                "site_country": (row.get("Site country") or "").strip(),
                "site": (row.get("Site") or "").strip(),
                "business_unit": (row.get("Business unit") or "").strip(),
                "department": (row.get("Department") or "").strip(),
                "sub_department": (row.get("Sub department") or "").strip(),
                "job_title": (row.get("Job title") or "").strip(),
                "employment_type": (row.get("Employment type") or "").strip(),
                "lifecycle_status": (row.get("Lifecycle status") or "").strip(),
                "candidate_jobvite_id": (row.get("Candidate Jobvite ID") or "").strip(),
                "start_date": (row.get("Start date") or "").strip(),
            }

        parsed = [parse(r) for r in tqdm(rows, desc="Parsing", unit="row")]
        parsed = [p for p in parsed if p["email"]]

        # Traer existentes en chunks de 500 para no colgar la query
        def chunked(lst, size):
            for i in range(0, len(lst), size):
                yield lst[i:i + size]

        self.stdout.write("Fetching existing records...")
        all_emails = [p["email"] for p in parsed]
        existing_map = {}
        for chunk in tqdm(list(chunked(all_emails, 500)), desc="Fetching", unit="chunk"):
            for obj in EmployeeDirectoryHiBob.objects.filter(email__in=chunk):
                existing_map[obj.email] = obj

        to_create = []
        to_update = []

        for data in parsed:
            email = data["email"]
            if email in existing_map:
                obj = existing_map[email]
                for field, value in data.items():
                    if field != "email":
                        setattr(obj, field, value)
                to_update.append(obj)
            else:
                to_create.append(EmployeeDirectoryHiBob(**data))

        update_fields = [
            "employee_id", "first_name", "last_name", "site_country", "site",
            "business_unit", "department", "sub_department", "job_title",
            "employment_type", "lifecycle_status", "candidate_jobvite_id", "start_date",
        ]

        self.stdout.write("Saving...")
        for chunk in tqdm(list(chunked(to_create, 500)), desc="Creating", unit="chunk"):
            EmployeeDirectoryHiBob.objects.bulk_create(chunk)

        for chunk in tqdm(list(chunked(to_update, 500)), desc="Updating", unit="chunk"):
            EmployeeDirectoryHiBob.objects.bulk_update(chunk, fields=update_fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed. Created: {len(to_create)}, Updated: {len(to_update)}"
            )
        )