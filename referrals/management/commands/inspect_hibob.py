from django.core.management.base import BaseCommand, CommandError

from referrals.services.hibob.client import HiBobClient
from referrals.services.hibob.fields import (
    build_complete_field_lookup,
    resolve_requested_fields,
    unresolved_model_fields,
)
from referrals.services.hibob.mapper import ALL_MODEL_FIELDS, get_field_value


class Command(BaseCommand):
    help = "Inspect the HiBob payload mapping without writing to PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-size",
            type=int,
            default=200,
            help="Number of employees used to calculate field coverage",
        )

    def handle(self, *args, **options):
        sample_size = options["sample_size"]
        if sample_size < 1:
            raise CommandError("--sample-size must be greater than zero")

        client = HiBobClient()

        try:
            metadata = client.get_fields_metadata()
            field_lookup = build_complete_field_lookup(metadata)
            requested_fields = resolve_requested_fields(metadata)
            employees = client.search_employees(requested_fields)
        except Exception as error:
            raise CommandError(str(error)) from error
        finally:
            client.close()

        sample = employees[:sample_size]

        self.stdout.write(f"Employees fetched: {len(employees)}")
        self.stdout.write(f"Employees inspected: {len(sample)}")
        self.stdout.write("\nPostgreSQL model mapping:")

        for model_field in ALL_MODEL_FIELDS:
            field_id = field_lookup.get(model_field)
            if not field_id:
                self.stdout.write(f"- {model_field}: NOT RESOLVED")
                continue

            prefer_human_readable = model_field not in {
                "employee_id",
                "email",
                "start_date",
                "termination_date",
                "candidate_jobvite_id",
            }

            present = sum(
                1
                for employee in sample
                if get_field_value(
                    employee,
                    field_id,
                    prefer_human_readable=prefer_human_readable,
                )
                not in (None, "")
            )

            self.stdout.write(
                f"- {model_field} <- {field_id}: "
                f"{present}/{len(sample)} values"
            )

        unresolved = unresolved_model_fields(metadata)
        if unresolved:
            self.stdout.write(
                self.style.WARNING(
                    "\nOptional fields not resolved: " + ", ".join(unresolved)
                )
            )

        if employees:
            keys = sorted(str(key) for key in employees[0].keys())
            self.stdout.write("\nFirst employee JSON keys (values hidden):")
            for key in keys:
                self.stdout.write(f"- {key}")

        self.stdout.write(
            self.style.SUCCESS(
                "\nInspection completed. PostgreSQL was not modified."
            )
        )
