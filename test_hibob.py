import json
import sys

import requests
from requests.auth import HTTPBasicAuth


# ==========================================================
# CREDENCIALES DE HIBOB
# ==========================================================

SERVICE_USER_ID = "SERVICE-41170"       # Coloca aquí el Service User ID
SERVICE_USER_TOKEN = "tUcsZIF75cXbb3jHMfwrW4QgUKCL6dowJskVGEGs"    # Coloca aquí el Service User Token

# Número de empleado que quieres buscar
EMPLOYEE_ID_IN_COMPANY = 50955

URL = "https://api.hibob.com/v1/people/search"

FIELDS = [
    "root.id",
    "root.firstName",
    "root.surname",
    "root.fullName",
    "root.displayName",
    "root.email",
    "work.employeeIdInCompany",
    "work.title",
    "work.department",
    "work.site",
    "work.reportsTo",
    "employment.startDate",
    "employment.status",
]


def extract_value(employee: dict, slash_path: str, nested_path: list[str]):
    flat_value = employee.get(slash_path)

    if isinstance(flat_value, dict):
        value = flat_value.get("value")
        if value is not None:
            return value

    current = employee

    for key in nested_path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def get_employee_number(employee: dict):
    return extract_value(
        employee,
        "/work/employeeIdInCompany",
        ["work", "employeeIdInCompany"],
    )


def get_employee_name(employee: dict):
    possible_names = [
        extract_value(employee, "/root/displayName", ["displayName"]),
        extract_value(employee, "/root/fullName", ["fullName"]),
        extract_value(
            employee,
            "/root/fullName",
            ["root", "fullName"],
        ),
        extract_value(
            employee,
            "/root/displayName",
            ["root", "displayName"],
        ),
    ]

    for name in possible_names:
        if name:
            return str(name)

    first_name = extract_value(
        employee,
        "/root/firstName",
        ["firstName"],
    )

    surname = extract_value(
        employee,
        "/root/surname",
        ["surname"],
    )

    full_name = " ".join(
        part for part in [first_name, surname] if part
    ).strip()

    return full_name or None


def search_employee(employee_number: int):
    payload = {
        "showInactive": True,
        "fields": FIELDS,
        "humanReadable": "APPEND",
    }

    response = requests.post(
        URL,
        auth=HTTPBasicAuth(
            SERVICE_USER_ID,
            SERVICE_USER_TOKEN,
        ),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )

    if not response.ok:
        print(f"Error HTTP {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()
    employees = data.get("employees", [])

    print(f"Empleados recibidos desde HiBob: {len(employees)}")

    for employee in employees:
        current_number = get_employee_number(employee)

        if str(current_number).strip() == str(employee_number).strip():
            return employee

    return None


def main():
    if "xxx" in (SERVICE_USER_ID, SERVICE_USER_TOKEN):
        print("Debes reemplazar las credenciales xxx.")
        sys.exit(1)

    employee = search_employee(EMPLOYEE_ID_IN_COMPANY)

    if employee is None:
        print(
            f"No se encontró employeeIdInCompany="
            f"{EMPLOYEE_ID_IN_COMPANY}"
        )
        return

    employee_name = get_employee_name(employee)

    print("\nEmpleado encontrado")
    print(f"Employee ID: {EMPLOYEE_ID_IN_COMPANY}")

    if employee_name:
        print(f"Nombre: {employee_name}")
    else:
        print("Nombre: no fue devuelto por HiBob")
        print(
            "Revisa el permiso del Service User para la "
            "categoría 'Basic info'."
        )

    print("\nRespuesta completa:\n")
    print(json.dumps(employee, indent=4, ensure_ascii=False))

    filename = f"empleado_{EMPLOYEE_ID_IN_COMPANY}.json"

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            employee,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(f"\nInformación guardada en: {filename}")


if __name__ == "__main__":
    main()