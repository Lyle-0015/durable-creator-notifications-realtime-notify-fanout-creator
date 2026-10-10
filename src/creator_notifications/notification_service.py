from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from .infrai_client import InfraiClient, InfraiError


class AssetDelivery(BaseModel):
    asset_id: str
    download_url: str


class SubscriberUpdate(BaseModel):
    creator_id: str
    tier: str


class ContentProcessing(BaseModel):
    content_id: str
    state: Literal["queued", "processing", "ready"]


class NotificationRequest(BaseModel):
    notification_id: str
    user_id: str
    kind: Literal["asset.delivery", "subscriber.updated", "content.processed"]
    asset: AssetDelivery | None = None
    subscriber: SubscriberUpdate | None = None
    content: ContentProcessing | None = None


class QueueResult(BaseModel):
    notification_id: str
    state: Literal["queued"]


class DeliveryResult(BaseModel):
    state: Literal["offline", "delivered"]
    delivered: int = 0


def get_client() -> InfraiClient:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is required")
    return InfraiClient(key)


app = FastAPI(title="Durable creator notifications")


def _payload(notification: NotificationRequest) -> dict[str, Any]:
    detail = {
        "asset.delivery": notification.asset,
        "subscriber.updated": notification.subscriber,
        "content.processed": notification.content,
    }[notification.kind]
    if detail is None:
        raise HTTPException(status_code=422, detail=f"{notification.kind} detail is required")
    return {
        "notification_id": notification.notification_id,
        "user_id": notification.user_id,
        "channel": f"creator:{notification.user_id}",
        "event": notification.kind,
        "data": detail.model_dump(),
    }


@app.post("/notifications", response_model=QueueResult, status_code=202)
def enqueue_notification(
    notification: NotificationRequest,
    client: InfraiClient = Depends(get_client),
) -> QueueResult:
    try:
        client.queue_notification(_payload(notification), notification.notification_id)
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return QueueResult(notification_id=notification.notification_id, state="queued")


@app.post("/deliver/{user_id}", response_model=DeliveryResult)
def deliver_waiting_notifications(
    user_id: str,
    client: InfraiClient = Depends(get_client),
) -> DeliveryResult:
    channel = f"creator:{user_id}"
    try:
        presence = client.presence(channel)
        if not presence.get("participants"):
            return DeliveryResult(state="offline")

        batch = client.consume(max_messages=10, visibility_timeout=30)
        messages = batch.get("messages", [])
        delivered = 0
        for message in messages:
            payload = message["payload"]
            if payload["user_id"] != user_id:
                continue
            client.publish_realtime(
                payload["channel"], payload["event"], payload["data"], message["message_id"]
            )
            delivered += 1
        return DeliveryResult(state="delivered", delivered=delivered)
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
