from __future__ import annotations

import json
import logging
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
        )
        self._is_authenticated = False

    async def close(self) -> None:
        await self._client.aclose()

    async def ensure_authenticated(self) -> None:
        if self._is_authenticated:
            return

        try:
            response = await self._client.post(
                "/login",
                data={
                    "username": self._settings.xui_username,
                    "password": self._settings.xui_password,
                },
            )
        except httpx.HTTPError as exc:
            raise XUIUnavailableError("Failed to reach 3x-ui during login") from exc

        if response.status_code >= 400:
            raise XUIAuthError(f"3x-ui login failed with status {response.status_code}")

        if "login" in str(response.url).lower() and not self._client.cookies:
            raise XUIAuthError("3x-ui login did not establish a session")

        self._is_authenticated = True
        logger.info("Authenticated against 3x-ui")

    async def get_inbounds(self) -> list[dict]:
        payload = await self._request("GET", "/panel/api/inbounds/list")
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
        payload_client = {
            "id": client_uuid,
            "email": email,
            "enable": True,
            "flow": self._settings.vpn_flow,
            "limitIp": 0,
            "expiryTime": self._to_millis(expires_at),
            "totalGB": 0,
            "subId": "",
            "tgId": "",
            "reset": 0,
        }
        payload = {
            "id": self._settings.xui_inbound_id,
            "settings": json.dumps({"clients": [payload_client]}),
        }

        await self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        created = await self.get_client(email=email, inbound_id=self._settings.xui_inbound_id)
        return created

    async def delete_client(self, *, inbound_id: int, client_id: str) -> None:
        await self._request(
            "POST",
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
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
            "settings": json.dumps(
                {
                    "clients": [
                        {
                            "id": client_id,
                            "email": email,
                            "enable": enabled,
                            "flow": self._settings.vpn_flow,
                            "limitIp": 0,
                            "expiryTime": self._to_millis(expires_at),
                            "totalGB": 0,
                            "subId": "",
                            "tgId": "",
                            "reset": 0,
                        }
                    ]
                }
            ),
        }
        await self._request(
            "POST",
            f"/panel/api/inbounds/updateClient/{client_id}",
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
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise XUIUnavailableError(f"3x-ui request failed for {path}") from exc

        if response.status_code == 401:
            self._is_authenticated = False
            raise XUIAuthError("3x-ui session expired or is invalid")
        if response.status_code >= 400:
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
            raise XUIError(payload.get("msg") or f"3x-ui request failed for {path}")
        return payload

    @staticmethod
    def _to_millis(value: datetime) -> int:
        return int(value.astimezone(timezone.utc).timestamp() * 1000)
