from __future__ import annotations

import json
import logging
import ssl
import uuid as uuid_lib
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class XUIError(Exception):
    """Base 3x-ui error."""


class XUIAuthError(XUIError):
    """Raised when authentication to 3x-ui fails."""


class XUIUnavailableError(XUIError):
    """Raised when 3x-ui cannot be reached or returns a bad response."""


class XUIClientNotFoundError(XUIError):
    """Raised when an XUI client cannot be found."""


@dataclass(slots=True)
class XUIManagedClient:
    client_id: str
    email: str
    uuid: str
    inbound_id: int
    expires_at: datetime
    enabled: bool


class XUIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.xui_base_url,
            timeout=settings.xui_request_timeout,
            follow_redirects=True,
            verify=settings.xui_verify_ssl,
        )
        self._is_authenticated = False

    async def close(self) -> None:
        await self._client.aclose()

    async def ensure_authenticated(self) -> None:
        if self._is_authenticated:
            return

        login_path = self._path("login")
        try:
            response = await self._client.post(
                login_path,
                data={
                    "username": self._settings.xui_username,
                    "password": self._settings.xui_password,
                },
            )
        except httpx.ConnectTimeout as exc:
            logger.exception(
                "3x-ui login timeout: url=%s timeout=%s",
                self._full_url(login_path),
                self._settings.xui_request_timeout,
            )
            raise XUIUnavailableError("Timed out while connecting to 3x-ui login endpoint") from exc
        except httpx.ReadTimeout as exc:
            logger.exception(
                "3x-ui login read timeout: url=%s timeout=%s",
                self._full_url(login_path),
                self._settings.xui_request_timeout,
            )
            raise XUIUnavailableError("Timed out while waiting for 3x-ui login response") from exc
        except httpx.ConnectError as exc:
            if self._is_ssl_error(exc):
                logger.exception(
                    "3x-ui login SSL error: url=%s verify_ssl=%s reason=%s",
                    self._full_url(login_path),
                    self._settings.xui_verify_ssl,
                    str(exc),
                )
                raise XUIUnavailableError("SSL error while connecting to 3x-ui login endpoint") from exc
            logger.exception(
                "3x-ui login connection error: url=%s verify_ssl=%s reason=%s",
                self._full_url(login_path),
                self._settings.xui_verify_ssl,
                str(exc),
            )
            raise XUIUnavailableError("Failed to connect to 3x-ui login endpoint") from exc
        except httpx.HTTPError as exc:
            logger.exception(
                "3x-ui login request error: url=%s verify_ssl=%s reason=%s",
                self._full_url(login_path),
                self._settings.xui_verify_ssl,
                str(exc),
            )
            raise XUIUnavailableError("Failed to reach 3x-ui during login") from exc

        if response.status_code >= 400:
            self._log_error_response("3x-ui login failed", response)
            if response.status_code == 401:
                raise XUIAuthError("3x-ui login returned 401 Unauthorized")
            if response.status_code == 404:
                raise XUIAuthError("3x-ui login endpoint returned 404 Not Found")
            raise XUIAuthError(f"3x-ui login failed with status {response.status_code}")

        if "login" in str(response.url).lower() and not self._client.cookies:
            self._log_error_response("3x-ui login did not establish a session", response)
            raise XUIAuthError("3x-ui login did not establish a session")

        self._is_authenticated = True
        logger.info(
            "Authenticated against 3x-ui: url=%s verify_ssl=%s",
            self._full_url(login_path),
            self._settings.xui_verify_ssl,
        )

    async def get_inbounds(self) -> list[dict]:
        payload = await self._request("GET", "panel/api/inbounds/list")
        if not isinstance(payload, dict):
            raise XUIUnavailableError("Unexpected 3x-ui response for inbounds list")
        obj = payload.get("obj", [])
        if not isinstance(obj, list):
            raise XUIUnavailableError("3x-ui inbounds payload has invalid shape")
        return obj

    async def get_inbound(self, inbound_id: int) -> dict:
        for inbound in await self.get_inbounds():
            if int(inbound.get("id", 0)) == inbound_id:
                return inbound
        raise XUIClientNotFoundError(f"Inbound {inbound_id} not found in 3x-ui")

    async def create_client(
        self,
        *,
        email: str,
        expires_at: datetime,
    ) -> XUIManagedClient:
        client_uuid = str(uuid_lib.uuid4())
        payload_client = self._build_client_payload(
            client_id=client_uuid,
            email=email,
            enabled=True,
            expires_at=expires_at,
        )
        payload = {
            "id": self._settings.xui_inbound_id,
            "settings": json.dumps({"clients": [payload_client]}),
        }

        await self._request("POST", "panel/api/inbounds/addClient", json=payload)
        # 3x-ui expects the current inbound settings to be mutated via addClient.
        created = await self.get_client(email=email, inbound_id=self._settings.xui_inbound_id)
        return created

    async def delete_client(self, *, inbound_id: int, client_id: str) -> None:
        await self._request(
            "POST",
            f"panel/api/inbounds/{inbound_id}/delClient/{client_id}",
        )

    async def update_client_expiry(
        self,
        *,
        inbound_id: int,
        client_id: str,
        email: str,
        expires_at: datetime,
        enabled: bool,
    ) -> XUIManagedClient:
        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [
                    self._build_client_payload(
                        client_id=client_id,
                        email=email,
                        enabled=enabled,
                        expires_at=expires_at,
                    )
                ]
            }),
        }
        await self._request(
            "POST",
            f"panel/api/inbounds/updateClient/{client_id}",
            json=payload,
        )
        return await self.get_client(email=email, inbound_id=inbound_id)

    async def get_client(self, *, email: str, inbound_id: int) -> XUIManagedClient:
        inbound = await self.get_inbound(inbound_id)
        settings_raw = inbound.get("settings", "{}")
        try:
            settings_payload = json.loads(settings_raw)
        except json.JSONDecodeError as exc:
            raise XUIUnavailableError("Failed to decode inbound settings from 3x-ui") from exc

        clients = settings_payload.get("clients", [])
        for client in clients:
            if client.get("email") != email:
                continue
            expiry_time = int(client.get("expiryTime") or 0)
            expires_at = (
                datetime.fromtimestamp(expiry_time / 1000, tz=timezone.utc)
                if expiry_time > 0
                else datetime.now(timezone.utc)
            )
            return XUIManagedClient(
                client_id=str(client.get("id")),
                email=str(client.get("email")),
                uuid=str(client.get("id")),
                inbound_id=inbound_id,
                expires_at=expires_at,
                enabled=bool(client.get("enable", True)),
            )

        raise XUIClientNotFoundError(f"Client with email {email} not found")

    async def check_connection(self) -> None:
        await self.ensure_authenticated()
        await self.get_inbounds()

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | None:
        await self.ensure_authenticated()
        normalized_path = self._path(path)
        try:
            response = await self._client.request(method, normalized_path, **kwargs)
        except httpx.ConnectTimeout as exc:
            logger.exception(
                "3x-ui request timeout: method=%s url=%s timeout=%s",
                method,
                self._full_url(normalized_path),
                self._settings.xui_request_timeout,
            )
            raise XUIUnavailableError(f"Timed out while connecting to 3x-ui endpoint {path}") from exc
        except httpx.ReadTimeout as exc:
            logger.exception(
                "3x-ui response timeout: method=%s url=%s timeout=%s",
                method,
                self._full_url(normalized_path),
                self._settings.xui_request_timeout,
            )
            raise XUIUnavailableError(f"Timed out while waiting for 3x-ui response from {path}") from exc
        except httpx.ConnectError as exc:
            if self._is_ssl_error(exc):
                logger.exception(
                    "3x-ui SSL error: method=%s url=%s verify_ssl=%s reason=%s",
                    method,
                    self._full_url(normalized_path),
                    self._settings.xui_verify_ssl,
                    str(exc),
                )
                raise XUIUnavailableError(f"3x-ui SSL error for {path}") from exc
            logger.exception(
                "3x-ui connection error: method=%s url=%s verify_ssl=%s reason=%s",
                method,
                self._full_url(normalized_path),
                self._settings.xui_verify_ssl,
                str(exc),
            )
            raise XUIUnavailableError(f"3x-ui connection failed for {path}") from exc
        except httpx.HTTPError as exc:
            logger.exception(
                "3x-ui request error: method=%s url=%s verify_ssl=%s reason=%s",
                method,
                self._full_url(normalized_path),
                self._settings.xui_verify_ssl,
                str(exc),
            )
            raise XUIUnavailableError(f"3x-ui request failed for {path}") from exc

        if response.status_code == 401:
            self._is_authenticated = False
            self._log_error_response("3x-ui returned 401 Unauthorized", response)
            raise XUIAuthError("3x-ui session expired or is invalid")
        if response.status_code == 404:
            self._log_error_response("3x-ui returned 404 Not Found", response)
            raise XUIUnavailableError(f"3x-ui endpoint not found: {path}")
        if response.status_code >= 400:
            self._log_error_response("3x-ui request failed", response)
            raise XUIUnavailableError(
                f"3x-ui request failed for {path} with status {response.status_code}"
            )
        if not response.text.strip():
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            raise XUIUnavailableError(f"3x-ui returned invalid JSON for {path}") from exc

        if isinstance(payload, dict) and payload.get("success") is False:
            self._log_error_response("3x-ui API returned success=false", response)
            raise XUIError(payload.get("msg") or f"3x-ui request failed for {path}")
        return payload

    @staticmethod
    def _path(path: str) -> str:
        return path.lstrip("/")

    def _build_client_payload(
        self,
        *,
        client_id: str,
        email: str,
        enabled: bool,
        expires_at: datetime,
    ) -> dict:
        return {
            "id": client_id,
            "email": email,
            "enable": enabled,
            "flow": self._settings.vpn_flow or "",
            "limitIp": 0,
            "expiryTime": self._to_millis(expires_at),
            "totalGB": 0,
            "subId": "",
            "tgId": "",
            "reset": 0,
        }

    def _full_url(self, path: str) -> str:
        return str(self._client.base_url.join(path))

    @staticmethod
    def _trim_response_text(text: str) -> str:
        compact = " ".join(text.split())
        return compact[:300]

    def _log_error_response(self, message: str, response: httpx.Response) -> None:
        logger.error(
            "%s: method=%s url=%s status_code=%s response=%s",
            message,
            response.request.method,
            response.request.url,
            response.status_code,
            self._trim_response_text(response.text),
        )

    @staticmethod
    def _is_ssl_error(exc: BaseException) -> bool:
        current: BaseException | None = exc
        while current is not None:
            if isinstance(current, ssl.SSLError):
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _to_millis(value: datetime) -> int:
        return int(value.astimezone(timezone.utc).timestamp() * 1000)
