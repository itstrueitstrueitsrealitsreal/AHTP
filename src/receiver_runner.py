import asyncio
import sys
import json
import os

sys.path.insert(0, ".")
import src.Services.Receiver as Receiver

LOG_FILE = os.path.join(os.getcwd(), "receiver_log.jsonl")


def handle_packet(seqno, channel_type, payload, timestamp):
    record = {
        "seqno": seqno,
        "channel_type": channel_type,
        "payload": payload,
        "timestamp": timestamp,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    channel_name = "RELIABLE" if channel_type == 0 else "UNRELIABLE"
    print(f"[RECV] {channel_name} | SeqNo={seqno} | Data='{payload}'", flush=True)


async def main():
    # Clear previous log at startup
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    print(
        f"[ReceiverRunner] Starting receiver on 0.0.0.0:4433, writing to {LOG_FILE}",
        flush=True,
    )
    await Receiver.create_receiver(local_port=4433, callback=handle_packet)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
