import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


# ============================================================
# CREDENCIALES
# ============================================================

SERVICE_USER_ID = "SERVICE-41170"
SERVICE_USER_TOKEN = "tUcsZIF75cXbb3jHMfwrW4QgUKCL6dowJskVGEGs"


# ============================================================
# EMPLEADO QUE QUIERES BUSCAR
# ============================================================

TARGET_EMAIL = "oscarbonilla70@gmail.com"

# Puedes colocar el Employee ID visible o dejarlo en None.
TARGET_EMPLOYEE_ID = 50955
# TARGET_EMPLOYEE_ID = None


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://api.hibob.com/v1"

METADATA_URL = f"{BASE_URL}/company/people/fields"
PEOPLE_SEARCH_URL = f"{BASE_URL}/people/search"

OUTPUT_DIRECTORY = Path("hibob_export")

# Cantidad de campos enviada por petición.
# Si HiBob responde 400 por tamaño, bájalo a 100 o 75.
FIELDS_PER_REQUEST = 150

REQUEST_TIMEOUT = 300
SLEEP_BETWEEN_REQUESTS = 1.5

SHOW_INACTIVE = True


# ============================================================
# SESIÓN HTTP
# ============================================================

session = requests.Session()
session.auth = HTTPBasicAuth(
    SERVICE_USER_ID,
    SERVICE_USER_TOKEN,
)

session.headers.update(
    {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def save_json(path: Path, content: Any) -> None:
    """Guarda contenido JSON con formato legible."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            content,
            file,
            ensure_ascii=False,
            indent=4,
            default=str,
        )


def normalize_text(value: Any) -> str:
    """Normaliza un valor para realizar comparaciones."""

    if value is None:
        return ""

    return str(value).strip().lower()


def chunks(items: list[str], size: int):
    """Divide una lista en grupos."""

    for index in range(0, len(items), size):
        yield items[index:index + size]


def request_json(
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    retries: int = 4,
) -> Any:
    """
    Ejecuta una petición y reintenta ante errores temporales
    o límites de velocidad.
    """

    for attempt in range(1, retries + 1):
        try:
            response = session.request(
                method=method,
                url=url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.RequestException as error:
            if attempt == retries:
                raise RuntimeError(
                    f"No fue posible conectar con HiBob: {error}"
                ) from error

            wait_time = attempt * 5
            print(
                f"Error de conexión. Reintentando en "
                f"{wait_time} segundos..."
            )
            time.sleep(wait_time)
            continue

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")

            try:
                wait_time = int(retry_after)
            except (TypeError, ValueError):
                wait_time = attempt * 10

            print(
                f"HiBob respondió 429. Esperando "
                f"{wait_time} segundos..."
            )
            time.sleep(wait_time)
            continue

        if response.status_code >= 500:
            if attempt == retries:
                raise RuntimeError(
                    f"Error HTTP {response.status_code}:\n"
                    f"{response.text}"
                )

            wait_time = attempt * 5
            print(
                f"HiBob respondió {response.status_code}. "
                f"Reintentando en {wait_time} segundos..."
            )
            time.sleep(wait_time)
            continue

        if not response.ok:
            raise RuntimeError(
                f"Error HTTP {response.status_code}:\n"
                f"{response.text}"
            )

        try:
            return response.json()
        except ValueError as error:
            raise RuntimeError(
                "HiBob respondió contenido que no es JSON:\n"
                f"{response.text[:1000]}"
            ) from error

    raise RuntimeError("La petición no pudo completarse.")


def unwrap_value(value: Any) -> Any:
    """
    Convierte:
        {\"value\": 50955}
    en:
        50955

    Conserva otros objetos completos.
    """

    if isinstance(value, dict) and set(value.keys()) == {"value"}:
        return value["value"]

    return value


def get_path_value(
    employee: dict,
    slash_path: str,
    nested_paths: list[list[str]] | None = None,
) -> Any:
    """
    Intenta obtener un valor desde la notación slash y luego
    desde posibles estructuras anidadas.
    """

    direct_value = employee.get(slash_path)

    if direct_value is not None:
        return unwrap_value(direct_value)

    for path in nested_paths or []:
        current: Any = employee

        for key in path:
            if not isinstance(current, dict):
                current = None
                break

            current = current.get(key)

        if current is not None:
            return current

    return None


def get_root_id(employee: dict) -> str | None:
    value = get_path_value(
        employee,
        "/root/id",
        [
            ["root", "id"],
            ["id"],
        ],
    )

    if value is None:
        return None

    return str(value)


def get_employee_email(employee: dict) -> str | None:
    value = get_path_value(
        employee,
        "/root/email",
        [
            ["root", "email"],
            ["email"],
            ["humanReadable", "email"],
            ["humanReadable", "root", "email"],
        ],
    )

    if value is None:
        return None

    return str(value)


def get_employee_number(employee: dict) -> Any:
    return get_path_value(
        employee,
        "/work/employeeIdInCompany",
        [
            ["work", "employeeIdInCompany"],
            ["humanReadable", "work", "employeeIdInCompany"],
        ],
    )


def get_employee_name(employee: dict) -> str | None:
    """Busca el nombre en todas las formas conocidas."""

    name_candidates = [
        get_path_value(
            employee,
            "/root/fullName",
            [
                ["root", "fullName"],
                ["fullName"],
                ["humanReadable", "fullName"],
                ["humanReadable", "root", "fullName"],
            ],
        ),
        get_path_value(
            employee,
            "/root/displayName",
            [
                ["root", "displayName"],
                ["displayName"],
                ["humanReadable", "displayName"],
                ["humanReadable", "root", "displayName"],
            ],
        ),
    ]

    for candidate in name_candidates:
        if candidate:
            return str(candidate)

    first_name = get_path_value(
        employee,
        "/root/firstName",
        [
            ["root", "firstName"],
            ["firstName"],
            ["humanReadable", "firstName"],
            ["humanReadable", "root", "firstName"],
        ],
    )

    surname = get_path_value(
        employee,
        "/root/surname",
        [
            ["root", "surname"],
            ["surname"],
            ["humanReadable", "surname"],
            ["humanReadable", "root", "surname"],
        ],
    )

    full_name = " ".join(
        str(part).strip()
        for part in (first_name, surname)
        if part
    ).strip()

    return full_name or None


# ============================================================
# METADATA
# ============================================================

def get_all_fields_metadata() -> list[dict]:
    """Consulta todos los campos definidos en HiBob."""

    print("Consultando metadata de campos...")

    response = request_json(
        "GET",
        METADATA_URL,
    )

    if isinstance(response, list):
        fields = response
    elif isinstance(response, dict):
        fields = response.get("fields", [])
    else:
        raise RuntimeError(
            "Formato inesperado en la respuesta de metadata."
        )

    valid_fields = [
        field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    ]

    print(f"Campos encontrados en metadata: {len(valid_fields)}")

    return valid_fields


def build_metadata_map(
    metadata: list[dict],
) -> dict[str, dict]:
    return {
        str(field["id"]): field
        for field in metadata
        if field.get("id")
    }


def get_searchable_field_ids(
    metadata: list[dict],
) -> list[str]:
    """
    Obtiene los IDs de campos que enviaremos a people/search.

    Se eliminan duplicados conservando el orden.
    """

    field_ids: list[str] = []
    seen: set[str] = set()

    # Estos campos son esenciales para unir y filtrar empleados.
    required_fields = [
        "root.id",
        "root.email",
        "root.firstName",
        "root.surname",
        "root.fullName",
        "root.displayName",
        "work.employeeIdInCompany",
    ]

    for field_id in required_fields:
        if field_id not in seen:
            seen.add(field_id)
            field_ids.append(field_id)

    for field in metadata:
        field_id = field.get("id")

        if not field_id:
            continue

        field_id = str(field_id)

        if field_id not in seen:
            seen.add(field_id)
            field_ids.append(field_id)

    return field_ids


# ============================================================
# CONSULTA Y UNIÓN DE EMPLEADOS
# ============================================================

def fetch_employee_batch(
    field_ids: list[str],
    batch_number: int,
    total_batches: int,
) -> list[dict]:

    payload = {
        "showInactive": SHOW_INACTIVE,
        "humanReadable": "APPEND",
        "fields": field_ids,
    }

    print(
        f"Petición {batch_number}/{total_batches}: "
        f"{len(field_ids)} campos..."
    )

    response = request_json(
        "POST",
        PEOPLE_SEARCH_URL,
        payload=payload,
    )

    employees = response.get("employees", [])

    if not isinstance(employees, list):
        raise RuntimeError(
            "La respuesta no contiene una lista válida de empleados."
        )

    print(f"  Empleados recibidos: {len(employees)}")

    return employees


def merge_dicts(target: dict, source: dict) -> dict:
    """
    Une diccionarios de forma recursiva para conservar los campos
    obtenidos en distintas peticiones.
    """

    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            merge_dicts(target[key], value)
        else:
            target[key] = value

    return target


def merge_employees(
    employee_store: dict[str, dict],
    employees: list[dict],
) -> None:
    """Une cada respuesta usando root.id como identificador."""

    for employee in employees:
        root_id = get_root_id(employee)

        if root_id is None:
            # Respaldo para no perder registros sin root.id.
            email = get_employee_email(employee)
            employee_number = get_employee_number(employee)

            root_id = (
                f"email:{normalize_text(email)}"
                if email
                else f"employee:{employee_number}"
            )

        if root_id not in employee_store:
            employee_store[root_id] = {}

        merge_dicts(
            employee_store[root_id],
            employee,
        )


# ============================================================
# ORGANIZACIÓN DEL JSON
# ============================================================

def field_id_from_response_key(key: str) -> str | None:
    """
    Convierte:
        /work/title
    en:
        work.title
    """

    if not key.startswith("/"):
        return None

    return key.lstrip("/").replace("/", ".")


def organize_machine_fields(
    employee: dict,
    metadata_map: dict[str, dict],
) -> dict:
    """
    Organiza los campos slash por categoría y utiliza los nombres
    visibles de la metadata.
    """

    categories: dict[str, dict] = {}

    for key, raw_value in employee.items():
        field_id = field_id_from_response_key(key)

        if field_id is None:
            continue

        metadata = metadata_map.get(field_id, {})

        category_name = (
            metadata.get("categoryDisplayName")
            or metadata.get("category")
            or field_id.split(".", 1)[0]
        )

        visible_name = (
            metadata.get("name")
            or field_id
        )

        categories.setdefault(category_name, {})

        categories[category_name][visible_name] = {
            "field_id": field_id,
            "value": unwrap_value(raw_value),
            "type": metadata.get("type"),
            "historical": metadata.get("historical"),
        }

    return categories


def organize_employee(
    employee: dict,
    metadata_map: dict[str, dict],
) -> dict:
    """
    Construye una estructura clara sin eliminar la respuesta
    original de HiBob.
    """

    return {
        "identification": {
            "hibob_root_id": get_root_id(employee),
            "employee_id_in_company": get_employee_number(employee),
            "email": get_employee_email(employee),
            "name": get_employee_name(employee),
        },
        "fields_by_category": organize_machine_fields(
            employee,
            metadata_map,
        ),
        "human_readable": employee.get("humanReadable", {}),
        "raw_hibob_response": employee,
    }


# ============================================================
# FILTROS
# ============================================================

def find_by_email(
    employees: list[dict],
    target_email: str,
) -> list[dict]:

    normalized_target = normalize_text(target_email)

    return [
        employee
        for employee in employees
        if normalize_text(get_employee_email(employee))
        == normalized_target
    ]


def find_by_employee_number(
    employees: list[dict],
    target_employee_id: Any,
) -> list[dict]:

    normalized_target = normalize_text(target_employee_id)

    return [
        employee
        for employee in employees
        if normalize_text(get_employee_number(employee))
        == normalized_target
    ]


def diagnose_target(employee: dict) -> dict:
    """Muestra cuáles datos esenciales sí respondió HiBob."""

    required = {
        "root.id": get_root_id(employee),
        "root.email": get_employee_email(employee),
        "name": get_employee_name(employee),
        "work.employeeIdInCompany": get_employee_number(employee),
    }

    returned = {
        key: value
        for key, value in required.items()
        if value not in (None, "")
    }

    missing = [
        key
        for key, value in required.items()
        if value in (None, "")
    ]

    return {
        "returned": returned,
        "missing_or_omitted": missing,
    }


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main() -> None:
    if (
        SERVICE_USER_ID.strip() == "xxx"
        or SERVICE_USER_TOKEN.strip() == "xxx"
    ):
        print(
            "Debes reemplazar SERVICE_USER_ID y "
            "SERVICE_USER_TOKEN."
        )
        sys.exit(1)

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        metadata = get_all_fields_metadata()

        save_json(
            OUTPUT_DIRECTORY / "01_metadata_campos.json",
            metadata,
        )

        metadata_map = build_metadata_map(metadata)
        all_field_ids = get_searchable_field_ids(metadata)

        save_json(
            OUTPUT_DIRECTORY / "02_ids_campos_solicitados.json",
            all_field_ids,
        )

        field_batches = list(
            chunks(
                all_field_ids,
                FIELDS_PER_REQUEST,
            )
        )

        print(
            f"\nTotal de campos que se intentarán consultar: "
            f"{len(all_field_ids)}"
        )
        print(
            f"Total de peticiones de empleados: "
            f"{len(field_batches)}\n"
        )

        employee_store: dict[str, dict] = {}

        for index, field_batch in enumerate(
            field_batches,
            start=1,
        ):
            employees = fetch_employee_batch(
                field_ids=field_batch,
                batch_number=index,
                total_batches=len(field_batches),
            )

            merge_employees(
                employee_store,
                employees,
            )

            if index < len(field_batches):
                time.sleep(SLEEP_BETWEEN_REQUESTS)

        raw_employees = list(employee_store.values())

        print(
            f"\nEmpleados únicos después de unir respuestas: "
            f"{len(raw_employees)}"
        )

        save_json(
            OUTPUT_DIRECTORY / "03_todos_usuarios_raw.json",
            {
                "total_employees": len(raw_employees),
                "employees": raw_employees,
            },
        )

        print("Organizando empleados por categorías...")

        organized_employees = [
            organize_employee(
                employee,
                metadata_map,
            )
            for employee in raw_employees
        ]

        save_json(
            OUTPUT_DIRECTORY / "04_todos_usuarios_organizados.json",
            {
                "total_employees": len(organized_employees),
                "employees": organized_employees,
            },
        )

        # ----------------------------------------------------
        # FILTRO POR EMAIL
        # ----------------------------------------------------

        email_matches = find_by_email(
            raw_employees,
            TARGET_EMAIL,
        )

        organized_email_matches = [
            organize_employee(
                employee,
                metadata_map,
            )
            for employee in email_matches
        ]

        email_result = {
            "search_type": "email",
            "search_value": TARGET_EMAIL,
            "matches": len(organized_email_matches),
            "employees": organized_email_matches,
        }

        save_json(
            OUTPUT_DIRECTORY / "05_resultado_por_email.json",
            email_result,
        )

        # ----------------------------------------------------
        # FILTRO POR EMPLOYEE ID
        # ----------------------------------------------------

        employee_id_matches: list[dict] = []

        if TARGET_EMPLOYEE_ID is not None:
            employee_id_matches = find_by_employee_number(
                raw_employees,
                TARGET_EMPLOYEE_ID,
            )

        organized_id_matches = [
            organize_employee(
                employee,
                metadata_map,
            )
            for employee in employee_id_matches
        ]

        employee_id_result = {
            "search_type": "employeeIdInCompany",
            "search_value": TARGET_EMPLOYEE_ID,
            "matches": len(organized_id_matches),
            "employees": organized_id_matches,
        }

        save_json(
            OUTPUT_DIRECTORY / "06_resultado_por_employee_id.json",
            employee_id_result,
        )

        # ----------------------------------------------------
        # RESUMEN EN CONSOLA
        # ----------------------------------------------------

        print("\n========================================")
        print("RESULTADO POR EMAIL")
        print("========================================")
        print(f"Email buscado: {TARGET_EMAIL}")
        print(f"Coincidencias: {len(email_matches)}")

        for employee in email_matches:
            print(
                json.dumps(
                    {
                        "root_id": get_root_id(employee),
                        "employee_id": get_employee_number(employee),
                        "email": get_employee_email(employee),
                        "name": get_employee_name(employee),
                        "diagnostic": diagnose_target(employee),
                    },
                    ensure_ascii=False,
                    indent=4,
                )
            )

        print("\n========================================")
        print("RESULTADO POR EMPLOYEE ID")
        print("========================================")
        print(f"Employee ID buscado: {TARGET_EMPLOYEE_ID}")
        print(f"Coincidencias: {len(employee_id_matches)}")

        for employee in employee_id_matches:
            print(
                json.dumps(
                    {
                        "root_id": get_root_id(employee),
                        "employee_id": get_employee_number(employee),
                        "email": get_employee_email(employee),
                        "name": get_employee_name(employee),
                        "diagnostic": diagnose_target(employee),
                    },
                    ensure_ascii=False,
                    indent=4,
                )
            )

        print("\nProceso terminado.")
        print(
            f"Archivos generados en: "
            f"{OUTPUT_DIRECTORY.resolve()}"
        )

    except KeyboardInterrupt:
        print("\nProceso cancelado por el usuario.")
        sys.exit(1)

    except Exception as error:
        print(f"\nError: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()