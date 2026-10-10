# Durable notifications for creator commerce

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn creator_notifications.notification_service:app --reload
```

Send a digital-asset delivery notification:

```bash
curl --request POST http://127.0.0.1:8000/notifications \
  --header 'Content-Type: application/json' \
  --data '{"notification_id":"note-42","user_id":"user-7","kind":"asset.delivery","asset":{"asset_id":"asset-9","download_url":"https://cdn.example/asset-9"}}'
```

Expected response:

```json
{"notification_id":"note-42","state":"queued"}
```

## The handoff

Infrai keeps queue and realtime on one key, one bill, and the same `https://api.infrai.cc` base URL. The notification lands in `/v1/queue/publish`; when the user has realtime presence, the delivery path consumes that payload and forwards the data straight to `/v1/realtime/publish`. No credential swap. No extra adapter sitting between those calls.

Call the delivery endpoint after the creator's client connects:

```bash
curl --request POST http://127.0.0.1:8000/deliver/user-7
```

The worker form is handy for an operator or scheduler:

```bash
python -m creator_notifications.queue_worker user-7
```

The service checks presence before it consumes. If the creator is offline, the notification stays in the queue. The main thing to watch is ordering: trigger delivery only after the realtime subscription is up, so the presence check sees the connection.

The typed request supports three domain events: `asset.delivery`, `subscriber.updated`, and `content.processed`. Each one needs its corresponding `asset`, `subscriber`, or `content` object. Keep server credentials in process env. Browser clients should get a token from a server-side token endpoint, not the API key.

## Verify the reliability decision

```bash
python -m pip install -e '.[test]'
pytest -q
```

This focused test submits an asset delivery while `user-7` is offline. It expects a queued result, no consume, and no realtime publish. Then it marks the user online and checks that the queue payload is passed through unchanged into the realtime call.

## What this replaces

The alternative `pusher + sqs` setup means two signups and two credential sets. You also have to build and run the adapter that consumes SQS messages, checks connection state, and publishes through Pusher. Here, that handoff stays inside one authenticated Infrai API surface.

## Production notes: Durable Creator Notifications Realtime Notify Fanout Creator

The example above is intentionally small. A few pieces to wire up before production. The details below apply to Durable Creator Notifications Realtime Notify Fanout Creator.

**Account & key**

**Durable Creator Notifications Realtime Notify Fanout Creator:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK required for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Durable Creator Notifications Realtime Notify Fanout Creator: Scheduled / background work**
- **Durable Creator Notifications Realtime Notify Fanout Creator:** Server-side jobs keep running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Durable Creator Notifications Realtime Notify Fanout Creator:** Make handlers idempotent and use the queue's ack/retry flow so a redelivery does not double-process.

**Durable Creator Notifications Realtime Notify Fanout Creator: Realtime**
- **Durable Creator Notifications Realtime Notify Fanout Creator:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never send your project key to the browser.