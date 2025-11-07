import asyncio
import sys
import json
import os
import signal
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
    
    # Set up signal handler for graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        print("\n[ReceiverRunner] Shutdown signal received, computing metrics...", flush=True)
        shutdown_event.set()
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await Receiver.create_receiver(local_port=4433, callback=handle_packet)
        await shutdown_event.wait()
    finally:
        # Compute and print metrics before shutdown
        recv_api = Receiver.get_latest_api()
        if recv_api:
            recv_api.compute_metrics(label="Receiver-side")
        print("[ReceiverRunner] Shutdown complete", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
