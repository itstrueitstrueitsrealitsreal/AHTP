import asyncio
import sys
import json
import os
sys.path.insert(0, '.')
import src.Services.Receiver as Receiver

IPC_FILE = os.path.join(os.getcwd(), "current_log.txt")
DEFAULT_LOG_FILE = os.path.join(os.getcwd(), "receiver_log.jsonl")

def get_log_filename():
    if os.path.exists(IPC_FILE):
        try:
            with open(IPC_FILE, "r") as f:
                path = f.read().strip()
                if path:
                    return path
        except Exception:
            pass
    return DEFAULT_LOG_FILE


def handle_packet(seqno, channel_type, payload, timestamp):
    LOG_FILE = get_log_filename()
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
    print(f"[ReceiverRunner] Starting receiver on 0.0.0.0:4433", flush=True)
    await Receiver.create_receiver(local_port=4433, callback=handle_packet)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
