from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from referrals.models import JobviteRequisitionReferralDetail


class Command(BaseCommand):
    help = "Sync requisition referral details from Excel report"

    def handle(self, *args, **kwargs):
        base_dir = Path.cwd()
        file_path = base_dir / "files" / "requisitions-referral-details.csv"

        if not file_path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        df = pd.read_csv(file_path)
        df = df.fillna("")

        required_columns = [
            "Req ID",
            "Recruiter (req)",
            "Workflow title",
            "Hiring manager",
            "Interviewer Full Name",
        ]

        missing_columns = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            self.stdout.write(
                self.style.ERROR(
                    f"Missing columns: {', '.join(missing_columns)}"
                )
            )
            self.stdout.write(f"Available columns: {list(df.columns)}")
            return

        records = []

        for _, row in df.iterrows():
            req_id = str(row["Req ID"]).strip()

            if not req_id:
                continue

            records.append(
                JobviteRequisitionReferralDetail(
                    req_id=req_id,
                    recruiter_name=str(row["Recruiter (req)"]).strip(),
                    workflow_title=str(row["Workflow title"]).strip(),
                    hiring_manager_name=str(row["Hiring manager"]).strip(),
                    interviewer_full_name=str(row["Interviewer Full Name"]).strip(),
                    raw_payload={
                        "Req ID": str(row["Req ID"]).strip(),
                        "Recruiter (req)": str(row["Recruiter (req)"]).strip(),
                        "Workflow title": str(row["Workflow title"]).strip(),
                        "Hiring manager": str(row["Hiring manager"]).strip(),
                        "Interviewer Full Name": str(row["Interviewer Full Name"]).strip(),
                    },
                )
            )

        self.stdout.write("Deleting previous records...")
        JobviteRequisitionReferralDetail.objects.all().delete()

        self.stdout.write("Creating records...")
        JobviteRequisitionReferralDetail.objects.bulk_create(records, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed. Created records: {len(records)}"
            )
        )