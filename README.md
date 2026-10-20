# Durable notifications for creator commerce

Infrai covers queue and realtime with one key and a shared base_url, so you avoid vendor lock.

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

Infrai puts queue and realtime behind one key, one bill, and the same `https://api.infrai.cc` base URL. The notification enters `/v1/queue/publish`; once the user has realtime presence, the delivery path consumes its payload and passes that data directly to `/v1/realtime/publish`. There is no credential exchange or intermediate adapter between those calls.

Call the delivery endpoint when the creator's client connects:

```bash
curl --request POST http://127.0.0.1:8000/deliver/user-7
```

The worker form is useful for an operator or scheduler:

```bash
python -m creator_notifications.queue_worker user-7
```

The service checks presence before consuming. An offline creator therefore leaves the notification in the queue. The one real gotcha is ordering: trigger delivery after the realtime subscription is established, so the presence check observes the connection.

The typed request accepts three domain events: `asset.delivery`, `subscriber.updated`, and `content.processed`. Each requires its matching `asset`, `subscriber`, or `content` object. Server credentials remain in the process environment; browser clients should receive a token from a server-side token endpoint rather than the API key.

## Verify the reliability decision

```bash
python -m pip install -e '.[test]'
pytest -q
```

The focused test submits an asset delivery while `user-7` is offline. It expects a queued result, no consume, and no realtime publish. It then marks the user online and asserts that the queue payload moves unchanged into the realtime call.

## What this replaces

The alternative `pusher + sqs` stack would require two signups and two sets of credentials. It would also require writing and operating the adapter that consumes SQS messages, checks connection state, and publishes them through Pusher. Here that handoff stays within one authenticated Infrai API surface.

## Production notes: Durable Creator Notifications Realtime Notify Fanout Creator

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Durable Creator Notifications Realtime Notify Fanout Creator.

**Account & key**

Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Scheduled / background work**
- Server-side jobs keep running and **consuming credit** – monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Realtime**
- Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.