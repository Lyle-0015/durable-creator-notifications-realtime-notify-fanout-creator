from __future__ import annotations

import argparse
import os

from .infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver queued notifications for a connected user")
    parser.add_argument("user_id")
    args = parser.parse_args()
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        parser.error("INFRAI_API_KEY is required")

    client = InfraiClient(key)
    channel = f"creator:{args.user_id}"
    try:
        if not client.presence(channel).get("participants"):
            print(f"{channel}: offline; notification remains queued")
            return
        messages = client.consume(max_messages=10, visibility_timeout=30).get("messages", [])
        delivered = 0
        for message in messages:
            payload = message["payload"]
            if payload["user_id"] == args.user_id:
                client.publish_realtime(
                    payload["channel"], payload["event"], payload["data"], message["message_id"]
                )
                delivered += 1
        print(f"{channel}: delivered {delivered}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
