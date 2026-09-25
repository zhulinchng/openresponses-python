from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType

import httpx

from .config import ClientConfig, WebSocketConfig
from .resources import AsyncResponses, Responses
from .websocket import AsyncWebSocketConnection, WebSocketConnection


class OpenResponses:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        default_headers: Mapping[str, str] | None = None,
        auth_header: str = "Authorization",
        auth_prefix: str | None = "Bearer",
        max_response_bytes: int = 16 * 1024 * 1024,
        response_compatibility: str = "strict",
        websocket_config: WebSocketConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = ClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            default_headers=dict(default_headers or {}),
            auth_header=auth_header,
            auth_prefix=auth_prefix,
            max_response_bytes=max_response_bytes,
            response_compatibility=response_compatibility,
        )
        self._owns_client = http_client is None
        self.websocket_config = websocket_config or WebSocketConfig.from_client(self.config)
        self._client = http_client or httpx.Client(timeout=self.config.timeout)
        self.responses = Responses(self._client, self.config)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenResponses:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def websocket(self) -> WebSocketConnection:
        return WebSocketConnection(self.config, self.websocket_config)


class AsyncOpenResponses:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        default_headers: Mapping[str, str] | None = None,
        auth_header: str = "Authorization",
        max_response_bytes: int = 16 * 1024 * 1024,
        response_compatibility: str = "strict",
        websocket_config: WebSocketConfig | None = None,
        auth_prefix: str | None = "Bearer",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = ClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            default_headers=dict(default_headers or {}),
            auth_header=auth_header,
            auth_prefix=auth_prefix,
            max_response_bytes=max_response_bytes,
            response_compatibility=response_compatibility,
        )
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=self.config.timeout)
        self.responses = AsyncResponses(self._client, self.config)
        self.websocket_config = websocket_config or WebSocketConfig.from_client(self.config)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncOpenResponses:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def websocket(self) -> AsyncWebSocketConnection:
        return AsyncWebSocketConnection(self.config, self.websocket_config)


__all__ = ["AsyncOpenResponses", "OpenResponses"]
