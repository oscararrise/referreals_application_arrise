import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from users.models import Administrador


class Command(BaseCommand):
    help = 'Import administrators from an Excel file into administradores table.'

    def add_arguments(self, parser):
        parser.add_argument(
    'file_path',
    nargs='?',
    default='files/portal_admins.xlsx',
    type=str,
    help='Path to the Excel file. Default: files/portal_admins.xlsx'
)

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            raise CommandError(f'Could not read file: {e}')

        required_columns = [
            'HiBobID',
            'email address',
            'Full name',
            'Known as Names',
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise CommandError(
                f'Missing required columns: {", ".join(missing_columns)}'
            )

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            hibob_id = str(row.get('HiBobID', '')).strip()
            email = str(row.get('email address', '')).strip().lower()
            full_name = str(row.get('Full name', '')).strip()
            known_as_name = str(row.get('Known as Names', '')).strip()

            if not hibob_id or not email or not full_name:
                skipped_count += 1
                continue

            admin_obj, created = Administrador.objects.update_or_create(
                email=email,
                defaults={
                    'hibob_id': hibob_id,
                    'full_name': full_name,
                    'known_as_name': known_as_name if known_as_name else None,
                    'is_active': True,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS('Import completed successfully.'))
        self.stdout.write(f'Created: {created_count}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Skipped: {skipped_count}')