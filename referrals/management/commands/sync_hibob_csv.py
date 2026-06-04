import csv
from datetime import datetime
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

        def parse_date(value):
            if not value:
                return None

            value = str(value).strip()

            if not value:
                return None

            formats = [
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%Y-%m-%d",
                "%d-%m-%Y",
                "%m-%d-%Y",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

            return None

        def get_value(row, *possible_names):
            for name in possible_names:
                value = row.get(name)

                if value is not None and str(value).strip():
                    return str(value).strip()

            return ""

        def parse(row):
            return {
                "email": get_value(row, "Email").lower(),
                "employee_id": get_value(row, "Employee ID"),
                "first_name": get_value(row, "First name"),
                "last_name": get_value(row, "Last name"),
                "site_country": get_value(row, "Site country"),
                "site": get_value(row, "Site"),
                "business_unit": get_value(row, "Business unit"),
                "entity": get_value(
                    row,
                    "Entity (Current)",
                    "Entity",
                    "Legal entity",
                    "Legal Entity",
                ),
                "department": get_value(row, "Department"),
                "sub_department": get_value(
                    row,
                    "Sub Department",
                    "Sub department",
                    "Sub-department",
                    "Subdepartment",
                ),
                "job_title": get_value(row, "Job title", "Job Title"),
                "employment_type": get_value(row, "Employment type", "Employment Type"),
                "lifecycle_status": get_value(row, "Lifecycle status", "Lifecycle Status"),
                "candidate_jobvite_id": get_value(row, "Candidate Jobvite ID"),
                "start_date": parse_date(get_value(row, "Start date", "Start Date")),
                "termination_date": parse_date(
                    get_value(row, "Termination date", "Termination Date")
                ),
            }

        parsed = [parse(row) for row in tqdm(rows, desc="Parsing", unit="row")]
        parsed = [item for item in parsed if item["email"]]

        def chunked(items, size):
            for index in range(0, len(items), size):
                yield items[index:index + size]

        self.stdout.write("Fetching existing records...")

        all_emails = [item["email"] for item in parsed]
        existing_map = {}

        for chunk in tqdm(list(chunked(all_emails, 500)), desc="Fetching", unit="chunk"):
            employees = EmployeeDirectoryHiBob.objects.filter(email__in=chunk)

            for employee in employees:
                existing_map[employee.email] = employee

        to_create = []
        to_update = []

        for data in parsed:
            email = data["email"]

            if email in existing_map:
                employee = existing_map[email]

                for field, value in data.items():
                    if field != "email":
                        setattr(employee, field, value)

                to_update.append(employee)
            else:
                to_create.append(EmployeeDirectoryHiBob(**data))

        update_fields = [
            "employee_id",
            "first_name",
            "last_name",
            "site_country",
            "site",
            "business_unit",
            "entity",
            "department",
            "sub_department",
            "job_title",
            "employment_type",
            "lifecycle_status",
            "candidate_jobvite_id",
            "start_date",
            "termination_date",
        ]

        self.stdout.write("Saving...")

        for chunk in tqdm(list(chunked(to_create, 500)), desc="Creating", unit="chunk"):
            EmployeeDirectoryHiBob.objects.bulk_create(chunk)

        for chunk in tqdm(list(chunked(to_update, 500)), desc="Updating", unit="chunk"):
            EmployeeDirectoryHiBob.objects.bulk_update(chunk, fields=update_fields)

        employees_with_entity = sum(1 for item in parsed if item["entity"])
        employees_with_termination_date = sum(
            1 for item in parsed if item["termination_date"]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed. Created: {len(to_create)}, Updated: {len(to_update)}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Employees with entity in CSV: {employees_with_entity}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Employees with termination date in CSV: {employees_with_termination_date}"
            )
        )