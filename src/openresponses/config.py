from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def normalize_base_url(base_url: str) -> str:
    value = base_url.rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https", "ws", "wss"} or not parts.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) or WS(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("base_url must not contain userinfo")
    if parts.query or parts.fragment:
        raise ValueError("base_url must not contain a query or fragment")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


@dataclass(frozen=True)
class ClientConfig:
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    timeout: float = 120.0
    default_headers: dict[str, str] | None = None
    auth_header: str = "Authorization"
    auth_prefix: str | None = "Bearer"
    max_response_bytes: int = 16 * 1024 * 1024
    response_compatibility: str = "strict"

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", normalize_base_url(self.base_url))
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if self.response_compatibility not in {"strict", "openai-compatible", "openai"}:
            raise ValueError("response_compatibility must be strict, openai-compatible, or openai")

    @property
    def responses_url(self) -> str:
        return f"{self.base_url}/responses"

    @property
    def compact_url(self) -> str:
        return f"{self.base_url}/responses/compact"

    def headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        result = dict(self.default_headers or {})
        if self.api_key:
            value = f"{self.auth_prefix} {self.api_key}" if self.auth_prefix else self.api_key
            result[self.auth_header] = value
        if extra:
            result.update(extra)
        return result


@dataclass(frozen=True)
class WebSocketConfig:
    open_timeout: float = 10.0
    close_timeout: float = 10.0
    ping_interval: float | None = 20.0
    ping_timeout: float | None = 20.0
    max_size: int | None = 16 * 1024 * 1024

    @classmethod
    def from_client(cls, client_config: ClientConfig) -> WebSocketConfig:
        del client_config
        return cls()
