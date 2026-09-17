import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth


# ============================================================
# CREDENCIALES HIBOB
# ============================================================

SERVICE_USER_ID = "SERVICE-41170"
SERVICE_USER_TOKEN = "tUcsZIF75cXbb3jHMfwrW4QgUKCL6dowJskVGEGs"




# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://api.hibob.com/v1"

FIELDS_METADATA_URL = f"{BASE_URL}/company/people/fields"
PEOPLE_SEARCH_URL = f"{BASE_URL}/people/search"

OUTPUT_FILE = Path("hibob_todos_los_empleados.xlsx")
RAW_JSON_FILE = Path("hibob_todos_los_empleados_raw.json")

# Número de campos enviados en cada petición.
# Si HiBob responde 400, prueba con 75 o 50.
FIELDS_PER_REQUEST = 100

SHOW_INACTIVE = True
HUMAN_READABLE = "APPEND"

REQUEST_TIMEOUT = 300
SECONDS_BETWEEN_REQUESTS = 2

# Empleado que deseas revisar adicionalmente
TARGET_EMAIL = "oscarbonilla70@gmail.com"

# Puedes dejarlo en None si solo buscarás por correo.
TARGET_EMPLOYEE_ID = 50955


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
# FUNCIONES HTTP
# ============================================================

def request_json(
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    max_retries: int = 5,
) -> Any:
    """
    Ejecuta una petición HTTP a HiBob con reintentos para
    errores temporales y rate limits.
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = session.request(
                method=method,
                url=url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.RequestException as error:
            if attempt == max_retries:
                raise RuntimeError(
                    f"No se pudo conectar con HiBob: {error}"
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
                wait_time = attempt * 15

            print(
                f"HiBob respondió 429. Esperando "
                f"{wait_time} segundos..."
            )

            time.sleep(wait_time)
            continue

        if response.status_code >= 500:
            if attempt == max_retries:
                raise RuntimeError(
                    f"Error HTTP {response.status_code}:\n"
                    f"{response.text[:2000]}"
                )

            wait_time = attempt * 10

            print(
                f"HiBob respondió {response.status_code}. "
                f"Reintentando en {wait_time} segundos..."
            )

            time.sleep(wait_time)
            continue

        if not response.ok:
            raise RuntimeError(
                f"Error HTTP {response.status_code}:\n"
                f"{response.text[:5000]}"
            )

        try:
            return response.json()

        except ValueError as error:
            raise RuntimeError(
                "HiBob respondió contenido no válido como JSON:\n"
                f"{response.text[:2000]}"
            ) from error

    raise RuntimeError("La petición no pudo completarse.")


# ============================================================
# METADATA DE CAMPOS
# ============================================================

def get_fields_metadata() -> list[dict]:
    print("Consultando metadata de campos...")

    response = request_json(
        "GET",
        FIELDS_METADATA_URL,
    )

    if isinstance(response, list):
        fields = response

    elif isinstance(response, dict):
        fields = response.get("fields", [])

    else:
        raise RuntimeError(
            "La metadata llegó en un formato inesperado."
        )

    fields = [
        field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    ]

    print(f"Campos encontrados: {len(fields)}")

    return fields


def get_field_ids(metadata: list[dict]) -> list[str]:
    """
    Obtiene todos los IDs de los campos, conservando el orden
    y eliminando duplicados.
    """

    essential_fields = [
        "root.id",
        "root.email",
        "root.firstName",
        "root.surname",
        "root.fullName",
        "root.displayName",
        "work.employeeIdInCompany",
    ]

    result: list[str] = []
    seen: set[str] = set()

    for field_id in essential_fields:
        if field_id not in seen:
            seen.add(field_id)
            result.append(field_id)

    for field in metadata:
        field_id = str(field["id"])

        if field_id not in seen:
            seen.add(field_id)
            result.append(field_id)

    return result


def split_list(items: list[str], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


# ============================================================
# EXTRACCIÓN DE EMPLEADOS
# ============================================================

def extract_root_id(employee: dict) -> str | None:
    """
    Extrae el ID raíz del empleado independientemente del
    formato utilizado por HiBob.
    """

    slash_value = employee.get("/root/id")

    if isinstance(slash_value, dict):
        slash_value = slash_value.get("value")

    if slash_value not in (None, ""):
        return str(slash_value)

    if employee.get("id") not in (None, ""):
        return str(employee["id"])

    root = employee.get("root")

    if isinstance(root, dict) and root.get("id") not in (None, ""):
        return str(root["id"])

    return None


def fetch_employee_batch(
    fields: list[str],
    batch_number: int,
    total_batches: int,
) -> list[dict]:

    payload = {
        "showInactive": SHOW_INACTIVE,
        "humanReadable": HUMAN_READABLE,
        "fields": fields,
    }

    print(
        f"Petición {batch_number}/{total_batches}: "
        f"{len(fields)} campos"
    )

    response = request_json(
        "POST",
        PEOPLE_SEARCH_URL,
        payload=payload,
    )

    employees = response.get("employees", [])

    if not isinstance(employees, list):
        raise RuntimeError(
            "HiBob no devolvió una lista válida de empleados."
        )

    print(f"  Empleados recibidos: {len(employees)}")

    return employees


def merge_nested_dict(
    destination: dict,
    source: dict,
) -> dict:
    """
    Une dos diccionarios conservando los campos recibidos en
    distintas peticiones.
    """

    for key, value in source.items():
        if (
            key in destination
            and isinstance(destination[key], dict)
            and isinstance(value, dict)
        ):
            merge_nested_dict(
                destination[key],
                value,
            )
        else:
            destination[key] = value

    return destination


def merge_employees(
    employee_store: dict[str, dict],
    employees: list[dict],
) -> None:
    """
    Une los empleados de cada petición utilizando root.id.
    """

    for position, employee in enumerate(employees):
        root_id = extract_root_id(employee)

        if root_id is None:
            # Respaldo para no descartar un registro inesperado.
            root_id = f"unknown_{position}_{len(employee_store)}"

        if root_id not in employee_store:
            employee_store[root_id] = {}

        merge_nested_dict(
            employee_store[root_id],
            employee,
        )


# ============================================================
# CONVERSIÓN DE VALORES
# ============================================================

def unwrap_value(value: Any) -> Any:
    """
    Convierte objetos del tipo:
        {"value": "Oscar"}
    en:
        "Oscar"
    """

    if isinstance(value, dict) and "value" in value:
        if len(value) == 1:
            return value["value"]

    return value


def excel_safe_value(value: Any) -> Any:
    """
    Convierte listas y diccionarios a texto JSON para que puedan
    almacenarse en una celda de Excel.
    """

    value = unwrap_value(value)

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    return str(value)


def flatten_dictionary(
    value: Any,
    parent_key: str = "",
    separator: str = ".",
) -> dict[str, Any]:
    """
    Aplana estructuras anidadas.

    Ejemplo:
        {"work": {"title": "Data Analyst"}}

    Resultado:
        {"work.title": "Data Analyst"}
    """

    flattened: dict[str, Any] = {}

    if isinstance(value, dict):
        for key, child_value in value.items():
            complete_key = (
                f"{parent_key}{separator}{key}"
                if parent_key
                else str(key)
            )

            child_value = unwrap_value(child_value)

            if isinstance(child_value, dict):
                flattened.update(
                    flatten_dictionary(
                        child_value,
                        complete_key,
                        separator,
                    )
                )

            elif isinstance(child_value, list):
                flattened[complete_key] = json.dumps(
                    child_value,
                    ensure_ascii=False,
                    default=str,
                )

            else:
                flattened[complete_key] = child_value

    else:
        flattened[parent_key] = excel_safe_value(value)

    return flattened


# ============================================================
# CONSTRUCCIÓN DE LA FILA DE EXCEL
# ============================================================

def metadata_column_name(
    field: dict,
    human_readable: bool = False,
) -> str:
    """
    Genera un encabezado descriptivo para Excel.

    Ejemplo:
        Work | Job Title | work.title
    """

    category = (
        field.get("categoryDisplayName")
        or field.get("category")
        or "Other"
    )

    visible_name = (
        field.get("name")
        or field.get("id")
        or "Unknown"
    )

    field_id = field.get("id", "")

    prefix = "HR" if human_readable else "RAW"

    return (
        f"{prefix} | {category} | "
        f"{visible_name} | {field_id}"
    )


def get_direct_field_value(
    employee: dict,
    field_id: str,
) -> Any:
    """
    Busca un campo en el formato slash y en el formato anidado.
    """

    slash_key = "/" + field_id.replace(".", "/")

    if slash_key in employee:
        return unwrap_value(employee[slash_key])

    current: Any = employee

    for part in field_id.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return unwrap_value(current)


def get_nested_value(
    value: Any,
    field_id: str,
) -> Any:
    current = value

    for part in field_id.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return unwrap_value(current)


def create_employee_row(
    employee: dict,
    metadata: list[dict],
) -> dict[str, Any]:
    """
    Construye una fila completa con valores internos y valores
    human-readable.
    """

    row: dict[str, Any] = {}

    root_id = extract_root_id(employee)

    row["HiBob Root ID"] = root_id

    human_readable = employee.get("humanReadable", {})

    for field in metadata:
        field_id = field["id"]

        raw_column = metadata_column_name(
            field,
            human_readable=False,
        )

        hr_column = metadata_column_name(
            field,
            human_readable=True,
        )

        raw_value = get_direct_field_value(
            employee,
            field_id,
        )

        hr_value = get_nested_value(
            human_readable,
            field_id,
        )

        row[raw_column] = excel_safe_value(raw_value)
        row[hr_column] = excel_safe_value(hr_value)

    return row


# ============================================================
# FILTROS
# ============================================================

def normalize(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def find_column_ending_with(
    dataframe: pd.DataFrame,
    field_id: str,
    prefix: str,
) -> str | None:

    expected_ending = f"| {field_id}"

    for column in dataframe.columns:
        if (
            column.startswith(prefix)
            and column.endswith(expected_ending)
        ):
            return column

    return None


# ============================================================
# FORMATO DE EXCEL
# ============================================================

def write_excel(
    employees_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    target_df: pd.DataFrame,
    returned_fields_df: pd.DataFrame,
) -> None:

    print(f"Creando Excel: {OUTPUT_FILE}")

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="xlsxwriter",
        engine_kwargs={
            "options": {
                "strings_to_urls": False,
                "constant_memory": True,
            }
        },
    ) as writer:

        employees_df.to_excel(
            writer,
            sheet_name="Empleados",
            index=False,
        )

        metadata_df.to_excel(
            writer,
            sheet_name="Metadata campos",
            index=False,
        )

        target_df.to_excel(
            writer,
            sheet_name="Mi empleado",
            index=False,
        )

        returned_fields_df.to_excel(
            writer,
            sheet_name="Cobertura campos",
            index=False,
        )

        workbook = writer.book

        header_format = workbook.add_format(
            {
                "bold": True,
                "font_color": "white",
                "bg_color": "#1F4E78",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )

        text_format = workbook.add_format(
            {
                "valign": "top",
            }
        )

        missing_format = workbook.add_format(
            {
                "bg_color": "#F4CCCC",
                "font_color": "#9C0006",
            }
        )

        returned_format = workbook.add_format(
            {
                "bg_color": "#D9EAD3",
                "font_color": "#274E13",
            }
        )

        for sheet_name, dataframe in [
            ("Empleados", employees_df),
            ("Metadata campos", metadata_df),
            ("Mi empleado", target_df),
            ("Cobertura campos", returned_fields_df),
        ]:
            worksheet = writer.sheets[sheet_name]

            worksheet.freeze_panes(1, 1)
            worksheet.autofilter(
                0,
                0,
                max(len(dataframe), 1),
                max(len(dataframe.columns) - 1, 0),
            )

            worksheet.set_row(
                0,
                45,
                header_format,
            )

            for column_number, column_name in enumerate(
                dataframe.columns
            ):
                worksheet.write(
                    0,
                    column_number,
                    column_name,
                    header_format,
                )

                # Limita anchos para evitar columnas gigantes.
                sample_lengths = (
                    dataframe[column_name]
                    .dropna()
                    .astype(str)
                    .head(100)
                    .map(len)
                    .tolist()
                )

                maximum_length = max(
                    [len(str(column_name))] + sample_lengths
                )

                width = min(
                    max(maximum_length + 2, 12),
                    35,
                )

                worksheet.set_column(
                    column_number,
                    column_number,
                    width,
                    text_format,
                )

        coverage_sheet = writer.sheets["Cobertura campos"]

        if not returned_fields_df.empty:
            status_column_index = (
                returned_fields_df.columns
                .get_loc("status")
            )

            status_letter = (
                chr(ord("A") + status_column_index)
                if status_column_index < 26
                else None
            )

            if status_letter:
                coverage_sheet.conditional_format(
                    f"{status_letter}2:"
                    f"{status_letter}{len(returned_fields_df) + 1}",
                    {
                        "type": "text",
                        "criteria": "containing",
                        "value": "RETURNED",
                        "format": returned_format,
                    },
                )

                coverage_sheet.conditional_format(
                    f"{status_letter}2:"
                    f"{status_letter}{len(returned_fields_df) + 1}",
                    {
                        "type": "text",
                        "criteria": "containing",
                        "value": "NOT RETURNED",
                        "format": missing_format,
                    },
                )

    print("Excel creado correctamente.")


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

    try:
        metadata = get_fields_metadata()
        field_ids = get_field_ids(metadata)

        field_batches = list(
            split_list(
                field_ids,
                FIELDS_PER_REQUEST,
            )
        )

        print(f"Campos que se intentarán consultar: {len(field_ids)}")
        print(f"Peticiones necesarias: {len(field_batches)}")

        employee_store: dict[str, dict] = {}

        for batch_number, field_batch in enumerate(
            field_batches,
            start=1,
        ):
            employees = fetch_employee_batch(
                field_batch,
                batch_number,
                len(field_batches),
            )

            merge_employees(
                employee_store,
                employees,
            )

            if batch_number < len(field_batches):
                time.sleep(SECONDS_BETWEEN_REQUESTS)

        all_employees = list(employee_store.values())

        print(
            f"Empleados únicos obtenidos: "
            f"{len(all_employees)}"
        )

        print("Guardando respaldo JSON...")

        with RAW_JSON_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {
                    "totalEmployees": len(all_employees),
                    "employees": all_employees,
                },
                file,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        print("Construyendo tabla completa...")

        rows: list[dict] = []

        for index, employee in enumerate(
            all_employees,
            start=1,
        ):
            rows.append(
                create_employee_row(
                    employee,
                    metadata,
                )
            )

            if index % 1000 == 0:
                print(
                    f"  Empleados procesados: "
                    f"{index}/{len(all_employees)}"
                )

        employees_df = pd.DataFrame(rows)

        # Ordena colocando primero las columnas importantes.
        priority_fields = [
            "root.id",
            "root.email",
            "root.firstName",
            "root.surname",
            "root.fullName",
            "root.displayName",
            "work.employeeIdInCompany",
            "work.title",
            "work.department",
            "work.site",
            "work.reportsTo.email",
        ]

        priority_columns = ["HiBob Root ID"]

        for field_id in priority_fields:
            raw_column = find_column_ending_with(
                employees_df,
                field_id,
                "RAW",
            )

            hr_column = find_column_ending_with(
                employees_df,
                field_id,
                "HR",
            )

            if raw_column:
                priority_columns.append(raw_column)

            if hr_column:
                priority_columns.append(hr_column)

        priority_columns = list(
            dict.fromkeys(priority_columns)
        )

        remaining_columns = [
            column
            for column in employees_df.columns
            if column not in priority_columns
        ]

        employees_df = employees_df[
            priority_columns + remaining_columns
        ]

        # ----------------------------------------------------
        # FILTRAR MI EMPLEADO
        # ----------------------------------------------------

        email_column = (
            find_column_ending_with(
                employees_df,
                "root.email",
                "RAW",
            )
            or find_column_ending_with(
                employees_df,
                "root.email",
                "HR",
            )
        )

        employee_id_column = (
            find_column_ending_with(
                employees_df,
                "work.employeeIdInCompany",
                "RAW",
            )
            or find_column_ending_with(
                employees_df,
                "work.employeeIdInCompany",
                "HR",
            )
        )

        target_mask = pd.Series(
            False,
            index=employees_df.index,
        )

        if email_column:
            target_mask = target_mask | (
                employees_df[email_column]
                .map(normalize)
                .eq(normalize(TARGET_EMAIL))
            )

        if (
            TARGET_EMPLOYEE_ID is not None
            and employee_id_column
        ):
            target_mask = target_mask | (
                employees_df[employee_id_column]
                .map(normalize)
                .eq(normalize(TARGET_EMPLOYEE_ID))
            )

        target_df = employees_df[target_mask].copy()

        print(
            f"Coincidencias para tu empleado: "
            f"{len(target_df)}"
        )

        # ----------------------------------------------------
        # METADATA
        # ----------------------------------------------------

        metadata_df = pd.DataFrame(metadata)

        preferred_metadata_columns = [
            "id",
            "name",
            "categoryDisplayName",
            "categoryId",
            "category",
            "jsonPath",
            "type",
            "historical",
            "description",
        ]

        metadata_columns = [
            column
            for column in preferred_metadata_columns
            if column in metadata_df.columns
        ]

        metadata_columns += [
            column
            for column in metadata_df.columns
            if column not in metadata_columns
        ]

        metadata_df = metadata_df[metadata_columns]

        # ----------------------------------------------------
        # COBERTURA DE CAMPOS
        # ----------------------------------------------------

        coverage_rows = []

        for field in metadata:
            field_id = field["id"]

            raw_column = find_column_ending_with(
                employees_df,
                field_id,
                "RAW",
            )

            hr_column = find_column_ending_with(
                employees_df,
                field_id,
                "HR",
            )

            raw_count = (
                int(employees_df[raw_column].notna().sum())
                if raw_column
                else 0
            )

            hr_count = (
                int(employees_df[hr_column].notna().sum())
                if hr_column
                else 0
            )

            maximum_count = max(
                raw_count,
                hr_count,
            )

            coverage_rows.append(
                {
                    "field_id": field_id,
                    "field_name": field.get("name"),
                    "category": field.get(
                        "categoryDisplayName"
                    ),
                    "type": field.get("type"),
                    "raw_values_returned": raw_count,
                    "human_readable_values_returned": hr_count,
                    "total_employees": len(employees_df),
                    "status": (
                        "RETURNED"
                        if maximum_count > 0
                        else "NOT RETURNED / NO PERMISSION"
                    ),
                }
            )

        returned_fields_df = pd.DataFrame(
            coverage_rows
        )

        returned_fields_df = returned_fields_df.sort_values(
            by=[
                "status",
                "category",
                "field_name",
            ],
            ascending=[
                True,
                True,
                True,
            ],
        )

        write_excel(
            employees_df=employees_df,
            metadata_df=metadata_df,
            target_df=target_df,
            returned_fields_df=returned_fields_df,
        )

        print("\n========================================")
        print("PROCESO FINALIZADO")
        print("========================================")
        print(f"Excel: {OUTPUT_FILE.resolve()}")
        print(f"JSON respaldo: {RAW_JSON_FILE.resolve()}")
        print(f"Empleados: {len(employees_df)}")
        print(f"Columnas: {len(employees_df.columns)}")
        print(f"Tu empleado: {len(target_df)} coincidencia(s)")

    except KeyboardInterrupt:
        print("\nProceso cancelado.")
        sys.exit(1)

    except Exception as error:
        print(f"\nError: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()