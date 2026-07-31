"""Synchronize HiBob employees into the existing PostgreSQL table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from referrals.models import EmployeeDirectoryHiBob

from .client import HiBobClient
from .fields import (
    build_complete_field_lookup,
    resolve_requested_fields,
    unresolved_model_fields,
)
from .mapper import ALL_MODEL_FIELDS, EmployeeMappingError, map_employee


UPDATE_FIELDS = tuple(
    field for field in ALL_MODEL_FIELDS if field != "employee_id"
)


@dataclass(frozen=True)
class HiBobSyncResult:
    fetched: int
    mapped: int
    skipped: int
    created: int
    updated: int
    unchanged: int
    unresolved_fields: tuple[str, ...]
    dry_run: bool


class HiBobEmployeeSyncService:
    def __init__(
        self,
        client: HiBobClient | None = None,
        batch_size: int = 500,
    ) -> None:
        self.client = client or HiBobClient()
        self._owns_client = client is None
        self.batch_size = batch_size

    def run(self, *, dry_run: bool = False) -> HiBobSyncResult:
        try:
            metadata = self.client.get_fields_metadata()
            field_lookup = build_complete_field_lookup(metadata)
            employees = self.client.search_employees(
                resolve_requested_fields(metadata)
            )
            mapped_rows, skipped = self._map_employees(
                employees,
                field_lookup,
            )
            plan = self._build_plan(mapped_rows, field_lookup)

            if not dry_run:
                self._write(
                    plan["to_create"],
                    plan["to_update"],
                    plan["update_fields"],
                )

            return HiBobSyncResult(
                fetched=len(employees),
                mapped=len(mapped_rows),
                skipped=skipped,
                created=len(plan["to_create"]),
                updated=len(plan["to_update"]),
                unchanged=plan["unchanged"],
                unresolved_fields=tuple(unresolved_model_fields(metadata)),
                dry_run=dry_run,
            )
        finally:
            if self._owns_client:
                self.client.close()

    def _map_employees(
        self,
        employees: list[dict[str, Any]],
        field_lookup: dict[str, str],
    ) -> tuple[list[dict[str, Any]], int]:
        rows: dict[str, dict[str, Any]] = {}
        emails: dict[str, str] = {}
        skipped = 0

        for employee in employees:
            try:
                data = map_employee(employee, field_lookup)
            except EmployeeMappingError:
                skipped += 1
                continue

            employee_id = data["employee_id"]
            email = data["email"]

            if employee_id in rows:
                raise RuntimeError(
                    f"Duplicate HiBob employee ID: {employee_id}"
                )

            previous_id = emails.get(email)
            if previous_id and previous_id != employee_id:
                raise RuntimeError(
                    f"Duplicate HiBob email across employees: {email}"
                )

            rows[employee_id] = data
            emails[email] = employee_id

        return list(rows.values()), skipped

    def _build_plan(
        self,
        mapped_rows: list[dict[str, Any]],
        field_lookup: dict[str, str],
    ) -> dict[str, Any]:
        existing = list(EmployeeDirectoryHiBob.objects.all())
        by_employee_id: dict[str, EmployeeDirectoryHiBob] = {}
        by_email: dict[str, EmployeeDirectoryHiBob] = {}

        for record in existing:
            employee_id = str(record.employee_id or "").strip()
            email = str(record.email or "").strip().lower()

            if employee_id:
                if employee_id in by_employee_id:
                    raise RuntimeError(
                        f"Duplicate PostgreSQL employee_id: {employee_id}"
                    )
                by_employee_id[employee_id] = record

            if email:
                by_email[email] = record

        updateable = [
            field for field in UPDATE_FIELDS if field in field_lookup
        ]
        to_create: list[EmployeeDirectoryHiBob] = []
        to_update: list[EmployeeDirectoryHiBob] = []
        unchanged = 0
        used_rows: set[int] = set()

        for data in mapped_rows:
            employee_id = data["employee_id"]
            email = data["email"]
            record = by_employee_id.get(employee_id) or by_email.get(email)

            if record is None:
                to_create.append(EmployeeDirectoryHiBob(**data))
                continue

            if record.pk in used_rows:
                raise RuntimeError(
                    "Multiple HiBob employees matched one PostgreSQL row"
                )
            used_rows.add(record.pk)

            email_owner = by_email.get(email)
            if email_owner and email_owner.pk != record.pk:
                raise RuntimeError(
                    f"Email already belongs to another row: {email}"
                )

            changed = False

            if record.employee_id != employee_id:
                record.employee_id = employee_id
                changed = True

            for field in updateable:
                new_value = data.get(field)
                if getattr(record, field) != new_value:
                    setattr(record, field, new_value)
                    changed = True

            if changed:
                record.updated_at = timezone.now()
                to_update.append(record)
            else:
                unchanged += 1

        return {
            "to_create": to_create,
            "to_update": to_update,
            "unchanged": unchanged,
            "update_fields": list(dict.fromkeys(
                ["employee_id", *updateable, "updated_at"]
            )),
        }

    @transaction.atomic
    def _write(
        self,
        to_create: list[EmployeeDirectoryHiBob],
        to_update: list[EmployeeDirectoryHiBob],
        update_fields: list[str],
    ) -> None:
        if to_create:
            EmployeeDirectoryHiBob.objects.bulk_create(
                to_create,
                batch_size=self.batch_size,
            )

        if to_update:
            EmployeeDirectoryHiBob.objects.bulk_update(
                to_update,
                fields=update_fields,
                batch_size=self.batch_size,
            )
