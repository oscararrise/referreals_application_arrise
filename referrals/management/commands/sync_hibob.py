from django.core.management.base import BaseCommand, CommandError

from referrals.services.hibob.sync_service import HiBobEmployeeSyncService


class Command(BaseCommand):
    help = "Sync HiBob employees into EmployeeDirectoryHiBob"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and compare data without writing to PostgreSQL",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Bulk insert/update batch size",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        if batch_size < 1:
            raise CommandError("--batch-size must be greater than zero")

        self.stdout.write(
            self.style.WARNING(
                "Running HiBob sync in DRY RUN mode"
                if dry_run
                else "Running HiBob sync"
            )
        )

        try:
            result = HiBobEmployeeSyncService(
                batch_size=batch_size,
            ).run(dry_run=dry_run)
        except Exception as error:
            raise CommandError(str(error)) from error

        self.stdout.write(f"Fetched: {result.fetched}")
        self.stdout.write(f"Mapped: {result.mapped}")
        self.stdout.write(f"Skipped: {result.skipped}")
        self.stdout.write(f"To create: {result.created}")
        self.stdout.write(f"To update: {result.updated}")
        self.stdout.write(f"Unchanged: {result.unchanged}")

        if result.unresolved_fields:
            self.stdout.write(
                self.style.WARNING(
                    "Optional fields not resolved from HiBob metadata: "
                    + ", ".join(result.unresolved_fields)
                )
            )

        message = (
            "Dry run completed. PostgreSQL was not modified."
            if result.dry_run
            else "HiBob synchronization completed."
        )
        self.stdout.write(self.style.SUCCESS(message))
