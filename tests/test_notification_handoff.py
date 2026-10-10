from fastapi.testclient import TestClient

from creator_notifications.notification_service import app, get_client


class RecordingClient:
    def __init__(self, online: bool = False) -> None:
        self.online = online
        self.queued = []
        self.published = []
        self.consumed = False

    def queue_notification(self, payload, request_id):
        self.queued.append((payload, request_id))
        return {"message_id": "msg-1"}

    def presence(self, channel):
        return {"participants": [{"id": "socket-1"}]} if self.online else {"participants": []}

    def consume(self, max_messages, visibility_timeout):
        self.consumed = True
        payload, _ = self.queued[0]
        return {"messages": [{"message_id": "msg-1", "payload": payload}]}

    def publish_realtime(self, channel, event, data, message_id):
        self.published.append((channel, event, data, message_id))
        return {}


def test_offline_notification_stays_queued_then_moves_unchanged_to_realtime():
    backend = RecordingClient()
    app.dependency_overrides[get_client] = lambda: backend
    client = TestClient(app)
    request = {
        "notification_id": "note-42",
        "user_id": "user-7",
        "kind": "asset.delivery",
        "asset": {"asset_id": "asset-9", "download_url": "https://cdn.example/asset-9"},
    }

    queued = client.post("/notifications", json=request)
    offline = client.post("/deliver/user-7")

    assert queued.json() == {"notification_id": "note-42", "state": "queued"}
    assert offline.json() == {"state": "offline", "delivered": 0}
    assert backend.consumed is False
    assert backend.published == []

    backend.online = True
    delivered = client.post("/deliver/user-7")

    assert delivered.json() == {"state": "delivered", "delivered": 1}
    payload = backend.queued[0][0]
    assert backend.published == [
        (payload["channel"], payload["event"], payload["data"], "msg-1")
    ]
    app.dependency_overrides.clear()
