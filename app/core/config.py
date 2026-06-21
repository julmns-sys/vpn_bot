from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        alias="ADMIN_IDS",
    )
    database_url: str = Field(alias="DATABASE_URL")

    xui_base_url: str = Field(alias="XUI_BASE_URL")
    xui_username: str = Field(alias="XUI_USERNAME")
    xui_password: str = Field(alias="XUI_PASSWORD")
    xui_inbound_id: int = Field(alias="XUI_INBOUND_ID")
    xui_request_timeout: float = Field(default=15.0, alias="XUI_REQUEST_TIMEOUT")
    xui_verify_ssl: bool = Field(default=False, alias="XUI_VERIFY_SSL")

    vpn_host: str = Field(alias="VPN_HOST")
    vpn_port: int = Field(alias="VPN_PORT")
    vpn_protocol: str = Field(
        default="vless",
        alias="VPN_PROTOCOL",
        validation_alias=AliasChoices("VPN_PROTOCOL", "VPN_PROTOPCOL"),
    )
    vpn_security: str = Field(default="reality", alias="VPN_SECURITY")
    vpn_type: str = Field(default="tcp", alias="VPN_TYPE")
    vpn_sni: str | None = Field(default=None, alias="VPN_SNI")
    vpn_host_header: str | None = Field(default=None, alias="VPN_HOST_HEADER")
    vpn_public_key: str | None = Field(default=None, alias="VPN_PUBLIC_KEY")
    vpn_short_id: str | None = Field(default=None, alias="VPN_SHORT_ID")
    vpn_flow: str | None = Field(default=None, alias="VPN_FLOW")
    vpn_fingerprint: str | None = Field(default=None, alias="VPN_FINGERPRINT")
    vpn_alpn: str | None = Field(default=None, alias="VPN_ALPN")
    vpn_path: str | None = Field(default=None, alias="VPN_PATH")
    vpn_spx: str | None = Field(default=None, alias="VPN_SPX")
    vpn_remark_prefix: str = Field(default="vpn", alias="VPN_REMARK_PREFIX")

    default_subscription_days: int = Field(
        default=30,
        alias="DEFAULT_SUBSCRIPTION_DAYS",
    )
    price_text: str = Field(default="VPN доступ: 50 руб / месяц", alias="PRICE_TEXT")
    payment_phone: str | None = Field(default=None, alias="PAYMENT_PHONE")
    plan_prices: Annotated[dict[int, int], NoDecode] = Field(
        default_factory=dict,
        alias="PLAN_PRICES",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Any) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped in {"[]", "null", "None"}:
                return []
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        raise ValueError("ADMIN_IDS must be a comma-separated string or list")

    @field_validator("plan_prices", mode="before")
    @classmethod
    def parse_plan_prices(cls, value: Any) -> dict[int, int]:
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            return {int(key): int(amount) for key, amount in value.items()}
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("PLAN_PRICES must decode into an object")
            return {int(key): int(amount) for key, amount in parsed.items()}
        raise ValueError("PLAN_PRICES must be a JSON object")

    @field_validator("xui_base_url")
    @classmethod
    def normalize_xui_base_url(cls, value: str) -> str:
        return value.rstrip("/") + "/"

    @field_validator(
        "vpn_sni",
        "vpn_host_header",
        "vpn_public_key",
        "vpn_short_id",
        "vpn_flow",
        "vpn_fingerprint",
        "vpn_alpn",
        "vpn_path",
        "vpn_spx",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
