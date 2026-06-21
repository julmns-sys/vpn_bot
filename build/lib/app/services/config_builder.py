from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import Settings


def build_vless_config(
    *,
    settings: Settings,
    uuid: str,
    email: str,
) -> str:
    query_params = {
        "type": settings.vpn_type,
        "security": settings.vpn_security,
    }
    optional_params = {
        "sni": settings.vpn_sni,
        "host": settings.vpn_host_header,
        "pbk": settings.vpn_public_key,
        "sid": settings.vpn_short_id,
        "fp": settings.vpn_fingerprint,
        "flow": settings.vpn_flow,
        "alpn": settings.vpn_alpn,
    }
    query_params.update(
        {key: value for key, value in optional_params.items() if value}
    )
    if settings.vpn_path:
        query_params["path"] = settings.vpn_path
    if settings.vpn_spx:
        query_params["spx"] = settings.vpn_spx

    query = urlencode(query_params)
    remark = settings.vpn_remark_prefix
    return (
        f"{settings.vpn_protocol}://{uuid}@{settings.vpn_host}:{settings.vpn_port}"
        f"?{query}#{remark}"
    )
