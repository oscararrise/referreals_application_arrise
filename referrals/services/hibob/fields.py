"""Field selection for the HiBob employee directory sync."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


# Stable HiBob fields that map directly to the existing Django model.
CORE_MODEL_FIELD_IDS: dict[str, str] = {
    "employee_id": "work.employeeIdInCompany",
    "email": "root.email",
    "first_name": "root.firstName",
    "last_name": "root.surname",
    "site": "work.site",
    "department": "work.department",
    "job_title": "work.title",
    "start_date": "work.startDate",
}

CORE_FIELD_IDS: tuple[str, ...] = tuple(CORE_MODEL_FIELD_IDS.values())


# These fields may be custom or renamed in each HiBob tenant. Their real IDs
# are discovered from /company/people/fields by matching display names.
MODEL_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "site_country": (
        "site country",
        "country of site",
    ),
    "business_unit": (
        "business unit",
        "business unit current",
    ),
    "entity": (
        "entity",
        "entity current",
        "legal entity",
    ),
    "sub_department": (
        "sub department",
        "sub-department",
        "subdepartment",
    ),
    "employment_type": (
        "employment type",
        "employee type",
    ),
    "lifecycle_status": (
        "lifecycle status",
        "employee status",
        "status",
    ),
    "termination_date": (
        "termination date",
        "end date",
    ),
    "candidate_jobvite_id": (
        "candidate jobvite id",
        "jobvite candidate id",
        "jobvite id",
    ),
}


def resolve_requested_fields(metadata: Iterable[dict[str, Any]]) -> list[str]:
    """Return only the HiBob field IDs needed by EmployeeDirectoryHiBob."""

    requested = list(CORE_FIELD_IDS)
    requested.extend(build_model_field_lookup(metadata).values())
    return list(dict.fromkeys(requested))


def build_complete_field_lookup(
    metadata: Iterable[dict[str, Any]],
) -> dict[str, str]:
    """Map every resolvable Django model field to a HiBob field ID."""

    result = dict(CORE_MODEL_FIELD_IDS)
    result.update(build_model_field_lookup(metadata))
    return result


def build_model_field_lookup(
    metadata: Iterable[dict[str, Any]],
) -> dict[str, str]:
    """Map tenant-specific Django model fields to real HiBob field IDs."""

    normalized_aliases = {
        model_field: {_normalize(alias) for alias in aliases}
        for model_field, aliases in MODEL_FIELD_ALIASES.items()
    }

    result: dict[str, str] = {}

    for item in metadata:
        if not isinstance(item, dict):
            continue

        field_id = str(item.get("id") or "").strip()
        field_name = _normalize(item.get("name"))

        if not field_id or not field_name:
            continue

        for model_field, aliases in normalized_aliases.items():
            if model_field not in result and field_name in aliases:
                result[model_field] = field_id

    return result


def unresolved_model_fields(
    metadata: Iterable[dict[str, Any]],
) -> list[str]:
    """Return optional model fields that could not be resolved in metadata."""

    resolved = build_model_field_lookup(metadata)
    return sorted(set(MODEL_FIELD_ALIASES) - set(resolved))


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())
