import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand

from referrals.models import ReferralBonusRule


class Command(BaseCommand):
    help = "Sync referral bonus rules from CSV file"

    def handle(self, *args, **kwargs):
        base_dir = Path.cwd()
        csv_path = base_dir / "files" / "referral_bonus_rules.csv"

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        with open(csv_path, mode="r", encoding="latin-1", newline="") as file:
            rows = list(csv.DictReader(file))

        def get_value(row, *possible_names):
            for name in possible_names:
                value = row.get(name)

                if value is not None and str(value).strip():
                    return str(value).strip()

            return ""

        def parse_date(value):
            if not value:
                return None

            value = str(value).strip()

            if not value or value in {"0", "-", "--"}:
                return None

            formats = [
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%d",
                "%m-%d-%Y",
                "%d-%m-%Y",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

            return None

        def parse_decimal(value):
            if not value:
                return None

            value = str(value).strip().replace(",", "")

            if not value or value in {"-", "--"}:
                return None

            try:
                return Decimal(value)
            except InvalidOperation:
                return None

        def parse_int(value):
            decimal_value = parse_decimal(value)

            if decimal_value is None:
                return None

            return int(decimal_value)

        records = []

        for row in rows:
            location = get_value(row, "Location of the referral")
            workflow_title = get_value(row, "Workflow title")

            if not location or not workflow_title:
                continue

            data = {
                "location_of_the_referral": location,
                "sub_department": get_value(row, "Sub department"),
                "workflow_title": workflow_title,
                "presenter_shuffler": get_value(row, "Presenter / shuffler"),
                "table_language": get_value(row, "Table language"),
                "full_time_part_time": get_value(row, "Full time / part time"),
                "date_effective": parse_date(get_value(row, "Date effective")),
                "date_end": parse_date(get_value(row, "Date end")),
                "bonus_amount_eur_gross": parse_decimal(
                    get_value(row, "Bonus amount (EUR gross)")
                ),
                "bonus_amount_eur_net": parse_decimal(
                    get_value(row, "Bonus amount (EUR net)")
                ),
                "pay_type": get_value(row, "Pay type"),
                "special_campaign_1st_installment": parse_decimal(
                    get_value(row, "Special campaign - 1st installment")
                ),
                "special_campaign_2nd_installment": parse_decimal(
                    get_value(row, "Special campaign - 2nd installment")
                ),
                "special_campaign_3rd_installment": parse_decimal(
                    get_value(row, "Special campaign - 3rd installment")
                ),
                "specificity": parse_int(get_value(row, "Specificity")),
                "rule_rank": parse_decimal(get_value(row, "Rule rank")),
                "raw_payload": dict(row),
            }

            records.append(ReferralBonusRule(**data))

        self.stdout.write("Deleting previous referral bonus rules...")
        ReferralBonusRule.objects.all().delete()

        self.stdout.write("Creating referral bonus rules...")
        ReferralBonusRule.objects.bulk_create(records, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed. Created referral bonus rules: {len(records)}"
            )
        )