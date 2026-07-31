"""Transform HiBob employee payloads into EmployeeDirectoryHiBob values."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


MODEL_FIELD_LIMITS: dict[str, int] = {
    "employee_id": 50,
    "email": 254,
    "first_name": 100,
    "last_name": 100,
    "site_country": 100,
    "site": 100,
    "business_unit": 100,
    "entity": 255,
    "department": 100,
    "sub_department": 100,
    "job_title": 255,
    "employment_type": 100,
    "lifecycle_status": 100,
    "candidate_jobvite_id": 100,
}

DATE_FIELDS = {"start_date", "termination_date"}

ALL_MODEL_FIELDS: tuple[str, ...] = (
    "employee_id",
    "email",
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
    "start_date",
    "termination_date",
    "candidate_jobvite_id",
)


class EmployeeMappingError(ValueError):
    """Raised when a HiBob employee cannot safely be stored."""


def map_employee(
    employee: dict[str, Any],
    field_lookup: dict[str, str],
) -> dict[str, Any]:
    """Map one HiBob employee into the existing PostgreSQL model shape."""

    mapped: dict[str, Any] = {}

    for model_field in ALL_MODEL_FIELDS:
        field_id = field_lookup.get(model_field)

        if not field_id:
            mapped[model_field] = None
            continue

        prefer_human_readable = model_field not in {
            "employee_id",
            "email",
            "start_date",
            "termination_date",
            "candidate_jobvite_id",
        }

        value = get_field_value(
            employee,
            field_id,
            prefer_human_readable=prefer_human_readable,
        )

        if model_field in DATE_FIELDS:
            mapped[model_field] = parse_date(value)
        else:
            mapped[model_field] = normalize_text(
                value,
                max_length=MODEL_FIELD_LIMITS.get(model_field),
            )

    if mapped.get("email"):
        mapped["email"] = mapped["email"].lower()

    if not mapped.get("employee_id"):
        raise EmployeeMappingError("Missing work.employeeIdInCompany")

    if not mapped.get("email"):
        raise EmployeeMappingError(
            f"Employee {mapped['employee_id']} has no email"
        )

    return mapped


def get_field_value(
    employee: dict[str, Any],
    field_id: str,
    *,
    prefer_human_readable: bool = False,
) -> Any:
    """Read a field from nested, dotted, or slash-style HiBob payloads."""

    human_readable = employee.get("humanReadable")

    containers: list[Any]
    if prefer_human_readable:
        containers = [human_readable, employee]
    else:
        containers = [employee, human_readable]

    for container in containers:
        if not isinstance(container, dict):
            continue

        value, found = _extract_field(container, field_id)
        if found:
            return unwrap_value(value)

    return None


def _extract_field(container: dict[str, Any], field_id: str) -> tuple[Any, bool]:
    direct_keys = (
        field_id,
        "/" + field_id.replace(".", "/"),
    )

    for key in direct_keys:
        if key in container:
            return container[key], True

    current: Any = container

    for part in field_id.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]

    return current, True


def unwrap_value(value: Any) -> Any:
    """Reduce common HiBob reference objects to a useful scalar value."""

    if isinstance(value, dict):
        for key in (
            "value",
            "displayName",
            "name",
            "title",
            "email",
            "id",
        ):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return unwrap_value(candidate)

    return value


def normalize_text(value: Any, max_length: int | None = None) -> str | None:
    value = unwrap_value(value)

    if value in (None, ""):
        return None

    if isinstance(value, list):
        text = ", ".join(
            item
            for item in (normalize_text(item) for item in value)
            if item
        )
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)

    text = " ".join(text.strip().split())

    if not text:
        return None

    if max_length is not None:
        text = text[:max_length]

    return text


def parse_date(value: Any) -> date | None:
    value = unwrap_value(value)

    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text or text in {"-", "--", "0"}:
        return None

    normalized_iso = text.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(normalized_iso).date()
    except ValueError:
        pass

    for date_format in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
    ):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue

    return None
