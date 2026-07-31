"""Field selection for the HiBob employee directory sync."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


# Stable HiBob field IDs used directly by the portal.
CORE_FIELD_IDS: tuple[str, ...] = (
    "root.id",
    "root.email",
    "root.firstName",
    "root.surname",
    "work.employeeIdInCompany",
    "work.title",
    "work.department",
    "work.site",
    "work.startDate",
)


# Some fields can be custom or renamed in each HiBob tenant. We discover
# their real field IDs from /company/people/fields using these display names.
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
    """Return the HiBob field IDs needed to populate EmployeeDirectoryHiBob.

    Core fields use stable IDs. Tenant-specific fields are resolved from the
    metadata display name, so no extra field IDs are required in the .env file.
    """

    metadata_items = [item for item in metadata if isinstance(item, dict)]
    available_ids = {
        str(item.get("id") or "").strip()
        for item in metadata_items
        if item.get("id")
    }

    requested: list[str] = []

    for field_id in CORE_FIELD_IDS:
        if field_id in available_ids:
            requested.append(field_id)

    lookup = build_model_field_lookup(metadata_items)
    requested.extend(lookup.values())

    return list(dict.fromkeys(requested))


def build_model_field_lookup(
    metadata: Iterable[dict[str, Any]],
) -> dict[str, str]:
    """Map Django model field names to their real HiBob field IDs."""

    normalized_aliases = {
        model_field: {_normalize(alias) for alias in aliases}
        for model_field, aliases in MODEL_FIELD_ALIASES.items()
    }

    result: dict[str, str] = {}

    for item in metadata:
        field_id = str(item.get("id") or "").strip()
        field_name = _normalize(item.get("name"))

        if not field_id or not field_name:
            continue

        for model_field, aliases in normalized_aliases.items():
            if model_field not in result and field_name in aliases:
                result[model_field] = field_id

    return result


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())
