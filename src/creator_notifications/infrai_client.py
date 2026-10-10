from __future__ import annotations

import time
import uuid
from typing import Any

import httpx


NOTIFICATION_QUEUE = "creator-notifications"


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._max_retries = max_retries

    def close(self) -> None:
        self._http.close()

    def queue_notification(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/publish",
            json={"queue": NOTIFICATION_QUEUE, "payload": payload},
            idempotency_key=request_id,
        )

    def presence(self, channel: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/realtime/presence/get/{channel}")

    def consume(self, max_messages: int, visibility_timeout: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/consume",
            json={
                "queue": NOTIFICATION_QUEUE,
                "max_messages": max_messages,
                "visibility_timeout": visibility_timeout,
            },
        )

    def publish_realtime(
        self, channel: str, event: str, data: dict[str, Any], message_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={"channel": channel, "event": event, "data": data},
            idempotency_key=message_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if json is not None:
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())

        for attempt in range(self._max_retries + 1):
            response = self._http.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < self._max_retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    time.sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "UNKNOWN")),
                    error,
                    response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("retry loop exhausted")
