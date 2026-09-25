"""Optional MLflow tracing for OpenResponses clients.

Import this module only when MLflow integration is desired. MLflow is not a
runtime dependency of the core package.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any

from ..client import AsyncOpenResponses, OpenResponses
from ..resources import AsyncResponses, Responses
from ..streaming import AsyncResponseStream, ResponseStream
from ..types.protocol import CreateResponseRequest


class _MLflowUnavailable(RuntimeError):
    pass


def _mlflow() -> Any:
    try:
        import mlflow  # type: ignore[import-not-found]
    except ImportError as exc:
        raise _MLflowUnavailable(
            "MLflow integration requires the optional 'mlflow' dependency"
        ) from exc
    return mlflow


def _payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, Mapping):
        return {key: _payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_payload(item) for item in value]
    return value


def _start(mlflow: Any, name: str, inputs: Any) -> Any:
    return mlflow.start_span(name=name, span_type="LLM", inputs=inputs)


class _TracedResponseStream:
    def __init__(self, stream: ResponseStream, span: Any) -> None:
        self._stream = stream
        self._span = span
        self._closed = False

    @property
    def final_response(self) -> Any:
        return self._stream.final_response

    @property
    def response_id(self) -> str | None:
        return self._stream.response_id

    @property
    def last_sequence_number(self) -> int | None:
        return self._stream.last_sequence_number

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        try:
            return next(self._stream)
        except StopIteration:
            self._finish()
            raise
        except BaseException as exc:
            self._span.__exit__(type(exc), exc, exc.__traceback__)
            raise

    def _finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._span.set_outputs(
            {"response": _payload(self._stream.final_response)}
            if self._stream.final_response
            else None
        )
        self._span.__exit__(None, None, None)

    def close(self) -> None:
        self._stream.close()
        self._finish()

    def __enter__(self) -> _TracedResponseStream:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class _TracedAsyncResponseStream:
    def __init__(self, stream: AsyncResponseStream, span: Any) -> None:
        self._stream = stream
        self._span = span
        self._closed = False

    @property
    def final_response(self) -> Any:
        return self._stream.final_response

    @property
    def response_id(self) -> str | None:
        return self._stream.response_id

    @property
    def last_sequence_number(self) -> int | None:
        return self._stream.last_sequence_number

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        try:
            return await self._stream.__anext__()
        except StopAsyncIteration:
            await self._finish()
            raise
        except BaseException as exc:
            self._span.__exit__(type(exc), exc, exc.__traceback__)
            raise

    async def _finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._span.set_outputs(
            {"response": _payload(self._stream.final_response)}
            if self._stream.final_response
            else None
        )
        self._span.__exit__(None, None, None)

    async def aclose(self) -> None:
        await self._stream.aclose()
        await self._finish()

    async def __aenter__(self) -> _TracedAsyncResponseStream:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


class _TracedResponses:
    def __init__(self, resource: Responses) -> None:
        self._resource = resource

    def create(self, request: CreateResponseRequest | Mapping[str, Any], **kwargs: Any) -> Any:
        mlflow = _mlflow()
        span = _start(mlflow, "openresponses.responses.create", _payload(request))
        span.__enter__()
        try:
            result = self._resource.create(request, **kwargs)
        except BaseException as exc:
            span.__exit__(type(exc), exc, exc.__traceback__)
            raise
        if isinstance(result, ResponseStream):
            return _TracedResponseStream(result, span)
        span.set_outputs({"response": _payload(result)})
        span.__exit__(None, None, None)
        return result

    def compact(self, request: Any, **kwargs: Any) -> Any:
        mlflow = _mlflow()
        span = _start(mlflow, "openresponses.responses.compact", _payload(request))
        span.__enter__()
        try:
            result = self._resource.compact(request, **kwargs)
        except BaseException as exc:
            span.__exit__(type(exc), exc, exc.__traceback__)
            raise
        span.set_outputs({"response": _payload(result)})
        span.__exit__(None, None, None)
        return result


class _TracedAsyncResponses:
    def __init__(self, resource: AsyncResponses) -> None:
        self._resource = resource

    async def create(
        self, request: CreateResponseRequest | Mapping[str, Any], **kwargs: Any
    ) -> Any:
        mlflow = _mlflow()
        span = _start(mlflow, "openresponses.responses.create", _payload(request))
        span.__enter__()
        try:
            result = await self._resource.create(request, **kwargs)
        except BaseException as exc:
            span.__exit__(type(exc), exc, exc.__traceback__)
            raise
        if isinstance(result, AsyncResponseStream):
            return _TracedAsyncResponseStream(result, span)
        span.set_outputs({"response": _payload(result)})
        span.__exit__(None, None, None)
        return result

    async def compact(self, request: Any, **kwargs: Any) -> Any:
        mlflow = _mlflow()
        span = _start(mlflow, "openresponses.responses.compact", _payload(request))
        span.__enter__()
        try:
            result = await self._resource.compact(request, **kwargs)
        except BaseException as exc:
            span.__exit__(type(exc), exc, exc.__traceback__)
            raise
        span.set_outputs({"response": _payload(result)})
        span.__exit__(None, None, None)
        return result


class MLflowOpenResponses:
    """Wrap an OpenResponses client with optional MLflow tracing."""

    def __init__(self, client: OpenResponses) -> None:
        self._client = client
        self.responses = _TracedResponses(client.responses)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def __enter__(self) -> MLflowOpenResponses:
        self._client.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        self._client.__exit__(*args)

    def close(self) -> None:
        self._client.close()


class MLflowAsyncOpenResponses:
    """Wrap an AsyncOpenResponses client with optional MLflow tracing."""

    def __init__(self, client: AsyncOpenResponses) -> None:
        self._client = client
        self.responses = _TracedAsyncResponses(client.responses)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def __aenter__(self) -> MLflowAsyncOpenResponses:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.__aexit__(*args)

    async def close(self) -> None:
        await self._client.close()


__all__ = ["MLflowAsyncOpenResponses", "MLflowOpenResponses"]
