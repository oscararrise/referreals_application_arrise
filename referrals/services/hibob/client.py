import os
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class HiBobClient:
    """Small client for the HiBob People API."""

    def __init__(
        self,
        service_user_id: str | None = None,
        service_user_token: str | None = None,
        base_url: str | None = None,
        timeout: int = 90,
        max_retries: int = 4,
    ) -> None:
        self.service_user_id = (
            service_user_id or os.getenv("HIBOB_SERVICE_USER_ID", "")
        ).strip()
        self.service_user_token = (
            service_user_token or os.getenv("HIBOB_SERVICE_USER_TOKEN", "")
        ).strip()
        self.base_url = (
            base_url
            or os.getenv("HIBOB_BASE_URL", "https://api.hibob.com/v1")
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.service_user_id:
            raise ValueError("HIBOB_SERVICE_USER_ID is required")

        if not self.service_user_token:
            raise ValueError("HIBOB_SERVICE_USER_TOKEN is required")

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(
            self.service_user_id,
            self.service_user_token,
        )
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def get_fields_metadata(self) -> list[dict[str, Any]]:
        """Return the fields visible to the configured service user."""
        payload = self._request_json(
            method="GET",
            endpoint="/company/people/fields",
        )

        if isinstance(payload, list):
            fields = payload
        elif isinstance(payload, dict):
            fields = payload.get("fields", [])
        else:
            raise RuntimeError("HiBob returned an invalid fields response")

        if not isinstance(fields, list):
            raise RuntimeError("HiBob returned an invalid fields list")

        return [
            field
            for field in fields
            if isinstance(field, dict) and field.get("id")
        ]

    def search_employees(
        self,
        fields: list[str],
        show_inactive: bool = True,
        human_readable: str = "APPEND",
    ) -> list[dict[str, Any]]:
        """Return employees for the requested HiBob field IDs."""
        payload = self._request_json(
            method="POST",
            endpoint="/people/search",
            json_body={
                "showInactive": show_inactive,
                "humanReadable": human_readable,
                "fields": fields,
            },
        )

        if not isinstance(payload, dict):
            raise RuntimeError("HiBob returned an invalid employee response")

        employees = payload.get("employees", [])

        if not isinstance(employees, list):
            raise RuntimeError("HiBob returned an invalid employees list")

        return [
            employee
            for employee in employees
            if isinstance(employee, dict)
        ]

    def close(self) -> None:
        self.session.close()

    def _request_json(
        self,
        method: str,
        endpoint: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json_body,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Could not connect to HiBob: {error}"
                    ) from error

                time.sleep(attempt * 5)
                continue

            if response.status_code == 429:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        "HiBob rate limit exceeded after all retries"
                    )

                time.sleep(self._retry_delay(response, attempt))
                continue

            if response.status_code >= 500:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"HiBob HTTP {response.status_code}: "
                        f"{response.text[:1000]}"
                    )

                time.sleep(attempt * 10)
                continue

            if not response.ok:
                raise RuntimeError(
                    f"HiBob HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )

            try:
                return response.json()
            except ValueError as error:
                raise RuntimeError(
                    f"HiBob returned invalid JSON: {response.text[:1000]}"
                ) from error

        raise RuntimeError("HiBob request could not be completed")

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> int:
        retry_after = response.headers.get("Retry-After")

        try:
            return int(retry_after) if retry_after else attempt * 15
        except ValueError:
            return attempt * 15
