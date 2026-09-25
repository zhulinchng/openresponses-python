from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import httpx

from .config import ClientConfig
from .errors import APIConnectionError, APITimeoutError
from .serialization import OpenAICompatibleResponse, parse_json_response, request_json, status_error
from .streaming import AsyncResponseStream, ResponseStream
from .types.generated import CompactResource, ResponseResource
from .types.openai import (
    OpenAICompactedResponse,
    OpenAICompactRequest,
    OpenAIRequest,
    OpenAIResponse,
)
from .types.protocol import CompactResponseRequest, CreateResponseRequest


class _Payloads:
    def _payload(
        self,
        request: CreateResponseRequest | OpenAIRequest | Mapping[str, Any],
        *,
        openai: bool,
    ) -> dict[str, Any]:
        if isinstance(request, OpenAIRequest):
            return request_json(request)
        if isinstance(request, CreateResponseRequest):
            if openai:
                return request_json(
                    OpenAIRequest.model_validate(
                        request.model_dump(mode="python", by_alias=True, exclude_unset=True)
                    )
                )
            return request_json(request)
        model = OpenAIRequest if openai else CreateResponseRequest
        return request_json(model.model_validate(request))

    def _compact_payload(
        self,
        request: CompactResponseRequest | OpenAICompactRequest | Mapping[str, Any],
        *,
        openai: bool,
    ) -> dict[str, Any]:
        if isinstance(request, OpenAICompactRequest):
            return request_json(request)
        if isinstance(request, CompactResponseRequest):
            if openai:
                return request_json(
                    OpenAICompactRequest.model_validate(
                        request.model_dump(mode="python", by_alias=True, exclude_unset=True)
                    )
                )
            return request_json(request)
        model = OpenAICompactRequest if openai else CompactResponseRequest
        return request_json(model.model_validate(request))


class Responses(_Payloads):
    def __init__(self, client: httpx.Client, config: ClientConfig) -> None:
        self._client = client
        self._config = config

    def create(
        self,
        request: CreateResponseRequest | OpenAIRequest | Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ResponseResource | OpenAICompatibleResponse | OpenAIResponse | ResponseStream:
        openai = self._config.response_compatibility == "openai"
        payload = self._payload(request, openai=openai)
        headers = self._config.headers(dict(extra_headers or {}))
        headers["Content-Type"] = "application/json"
        request_timeout = self._config.timeout if timeout is None else timeout
        if payload.get("stream"):
            return ResponseStream(
                self._client.stream(
                    "POST",
                    self._config.responses_url,
                    json=payload,
                    headers=headers,
                    timeout=request_timeout,
                ),
                self._config.response_compatibility,
                max_response_bytes=self._config.max_response_bytes,
            )
        try:
            response = self._client.post(
                self._config.responses_url,
                json=payload,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIConnectionError("request failed") from exc
        if not 200 <= response.status_code < 300:
            raise status_error(response, self._config.max_response_bytes)
        return cast(
            ResponseResource | OpenAICompatibleResponse | OpenAIResponse,
            parse_json_response(response, ResponseResource, self._config),
        )

    def compact(
        self,
        request: CompactResponseRequest | OpenAICompactRequest | Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> CompactResource | OpenAICompactedResponse:
        openai = self._config.response_compatibility == "openai"
        payload = self._compact_payload(request, openai=openai)
        headers = self._config.headers(dict(extra_headers or {}))
        headers["Content-Type"] = "application/json"
        request_timeout = self._config.timeout if timeout is None else timeout
        try:
            response = self._client.post(
                self._config.compact_url,
                json=payload,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIConnectionError("request failed") from exc
        if not 200 <= response.status_code < 300:
            raise status_error(response, self._config.max_response_bytes)
        return cast(
            CompactResource | OpenAICompactedResponse,
            parse_json_response(response, CompactResource, self._config),
        )


class AsyncResponses(_Payloads):
    def __init__(self, client: httpx.AsyncClient, config: ClientConfig) -> None:
        self._client = client
        self._config = config

    async def create(
        self,
        request: CreateResponseRequest | OpenAIRequest | Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ResponseResource | OpenAICompatibleResponse | OpenAIResponse | AsyncResponseStream:
        openai = self._config.response_compatibility == "openai"
        payload = self._payload(request, openai=openai)
        headers = self._config.headers(dict(extra_headers or {}))
        headers["Content-Type"] = "application/json"
        request_timeout = self._config.timeout if timeout is None else timeout
        if payload.get("stream"):
            return AsyncResponseStream(
                self._client.stream(
                    "POST",
                    self._config.responses_url,
                    json=payload,
                    headers=headers,
                    timeout=request_timeout,
                ),
                self._config.response_compatibility,
                max_response_bytes=self._config.max_response_bytes,
            )
        try:
            response = await self._client.post(
                self._config.responses_url,
                json=payload,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIConnectionError("request failed") from exc
        if not 200 <= response.status_code < 300:
            raise status_error(response, self._config.max_response_bytes)
        return cast(
            ResponseResource | OpenAICompatibleResponse | OpenAIResponse,
            parse_json_response(response, ResponseResource, self._config),
        )

    async def compact(
        self,
        request: CompactResponseRequest | OpenAICompactRequest | Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> CompactResource | OpenAICompactedResponse:
        openai = self._config.response_compatibility == "openai"
        payload = self._compact_payload(request, openai=openai)
        headers = self._config.headers(dict(extra_headers or {}))
        headers["Content-Type"] = "application/json"
        request_timeout = self._config.timeout if timeout is None else timeout
        try:
            response = await self._client.post(
                self._config.compact_url,
                json=payload,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIConnectionError("request failed") from exc
        if not 200 <= response.status_code < 300:
            raise status_error(response, self._config.max_response_bytes)
        return cast(
            CompactResource | OpenAICompactedResponse,
            parse_json_response(response, CompactResource, self._config),
        )
