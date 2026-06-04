import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from referrals.models import JobviteApplication


class Command(BaseCommand):
    help = "Sync Jobvite applications into local DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date-start",
            type=str,
            help="Start date in format MM-dd-yyyyTHH:mm:ssZ, example: 04-15-2026T00:00:00-0700",
        )
        parser.add_argument(
            "--date-end",
            type=str,
            help="End date in format MM-dd-yyyyTHH:mm:ssZ, example: 04-16-2026T23:59:59-0700",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Page size for Jobvite API",
        )
        parser.add_argument(
            "--full-sync",
            action="store_true",
            help="Force full sync using explicit date range",
        )
        parser.add_argument(
            "--page-sleep",
            type=int,
            default=1,
            help="Seconds to sleep between successful pages",
        )
        parser.add_argument(
            "--max-retries",
            type=int,
            default=4,
            help="Max retries per failed page",
        )

    def handle(self, *args, **options):
        base_url = getattr(
            settings,
            "JOBVITE_BASE_URL",
            "https://api.jobvite.com/api/v2/candidate",
        )
        api_key = getattr(settings, "JOBVITE_API_KEY", None)
        api_secret = getattr(settings, "JOBVITE_API_SECRET", None)
        company_id = getattr(settings, "JOBVITE_COMPANY_ID", "8128")

        if not api_key or not api_secret:
            self.stdout.write(
                self.style.ERROR("Missing JOBVITE_API_KEY or JOBVITE_API_SECRET in settings")
            )
            return

        date_start = options.get("date_start")
        date_end = options.get("date_end")
        count = options.get("count", 50)
        full_sync = options.get("full_sync", False)
        page_sleep = options.get("page_sleep", 1)
        max_retries = options.get("max_retries", 4)

        if not date_end:
            date_end = self._format_jobvite_datetime(timezone.now())

        if not date_start and not full_sync:
            last_local_update = (
                JobviteApplication.objects
                .exclude(last_updated_date__isnull=True)
                .order_by("-last_updated_date")
                .values_list("last_updated_date", flat=True)
                .first()
            )

            if last_local_update:
                date_start_dt = last_local_update - timedelta(minutes=5)
            else:
                date_start_dt = timezone.now() - timedelta(days=7)

            date_start = self._format_jobvite_datetime(date_start_dt)

        if not date_start:
            self.stdout.write(
                self.style.ERROR("You must provide --date-start when using --full-sync")
            )
            return

        headers = {
            "x-jvi-api": api_key,
            "x-jvi-sc": api_secret,
            "X-Company-Id": str(company_id),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        start = 1
        total_processed = 0
        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.WARNING(f"Syncing from {date_start} to {date_end}"))

        while True:
            params = {
                "format": "json",
                "start": start,
                "count": count,
                "dateFormat": "MM-dd-yyyy'T'HH:mm:ssZ",
                "datestart": date_start,
                "dateend": date_end,
            }

            response = self._fetch_with_retries(
                base_url=base_url,
                headers=headers,
                params=params,
                start=start,
                max_retries=max_retries,
            )

            if response is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"Jobvite API failed after retries at start={start}. Stopping sync safely."
                    )
                )
                break

            try:
                payload = response.json()
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid JSON at start={start}: {exc}. Body={response.text[:500]}"
                    )
                )
                break

            candidates = payload.get("candidates", [])

            if not isinstance(candidates, list):
                self.stdout.write(
                    self.style.ERROR(f"Unexpected response format at start={start}: {payload}")
                )
                break

            if not candidates:
                self.stdout.write("No more candidates returned. Finishing sync.")
                break

            self.stdout.write(f"Processing page start={start} | records={len(candidates)}")

            for item in candidates:
                try:
                    created = self._upsert_application(item)
                    total_processed += 1
                    if created:
                        total_created += 1
                    else:
                        total_updated += 1
                except Exception as exc:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping record on page start={start} due to error: {exc}"
                        )
                    )

            if len(candidates) < count:
                self.stdout.write("Last page reached. Finishing sync.")
                break

            start += count

            if page_sleep > 0:
                time.sleep(page_sleep)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={total_processed}, created={total_created}, updated={total_updated}"
            )
        )

    def _fetch_with_retries(
        self,
        base_url: str,
        headers: dict,
        params: dict,
        start: int,
        max_retries: int = 4,
    ) -> Optional[requests.Response]:
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(
                    base_url,
                    headers=headers,
                    params=params,
                    timeout=90,
                )

                if response.status_code == 200:
                    return response

                self.stdout.write(
                    self.style.WARNING(
                        f"Attempt {attempt}/{max_retries} failed at start={start} "
                        f"| status={response.status_code} | body={response.text[:300]}"
                    )
                )

            except requests.RequestException as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Attempt {attempt}/{max_retries} exception at start={start}: {exc}"
                    )
                )

            if attempt < max_retries:
                sleep_seconds = attempt * 5
                self.stdout.write(f"Sleeping {sleep_seconds}s before retry...")
                time.sleep(sleep_seconds)

        return None

    @transaction.atomic
    def _upsert_application(self, item: dict[str, Any]) -> bool:
        application = item.get("application", {}) or {}
        job = application.get("job", {}) or {}

        application_eid = application.get("eId")
        if not application_eid:
            raise ValueError("Missing application.eId in Jobvite payload")

        source = application.get("source")
        hibob_id = self._extract_hibob_id(source)

        defaults = {
            "candidate_eid": item.get("eId"),
            "email": item.get("email"),
            "first_name": item.get("firstName"),
            "last_name": item.get("lastName"),
            "mobile": item.get("mobile"),
            "source": source,
            "source_type": application.get("sourceType"),
            "hibob_id": hibob_id,
            "workflow_state": application.get("workflowState"),
            "workflow_state_eid": application.get("workflowStateEId"),
            "sent_date": self._epoch_ms_to_datetime(application.get("sentDate")),
            "last_updated_date": self._epoch_ms_to_datetime(application.get("lastUpdatedDate")),
            "job_eid": job.get("eId"),
            "requisition_id": job.get("requisitionId"),
            "job_title": job.get("title"),
            "department": job.get("department"),
            "location": job.get("location"),
            "posting_type": job.get("postingType"),
            "raw_payload": item,
        }

        _, created = JobviteApplication.objects.update_or_create(
            application_eid=application_eid,
            defaults=defaults,
        )
        return created

    def _extract_hibob_id(self, source: Optional[str]) -> Optional[str]:
        if not source:
            return None

        match = re.search(r"HiBobID[_:\s-]?(\d+)", source, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def _epoch_ms_to_datetime(self, value: Any) -> Optional[datetime]:
        if value in (None, "", 0):
            return None

        try:
            return datetime.fromtimestamp(
                int(value) / 1000,
                tz=timezone.get_current_timezone(),
            )
        except Exception:
            return None

    def _format_jobvite_datetime(self, dt: datetime) -> str:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        return dt.strftime("%m-%d-%YT%H:%M:%S%z")