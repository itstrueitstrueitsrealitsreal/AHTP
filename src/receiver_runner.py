import asyncio
import sys
import json
import os
import signal
import time
sys.path.insert(0, '.')
import src.Services.Receiver as Receiver

IPC_FILE = os.path.join(os.getcwd(), "current_log.txt")
DEFAULT_LOG_FILE = os.path.join(os.getcwd(), "receiver_log.jsonl")
METRICS_TRIGGER_FILE = os.path.join(os.getcwd(), "trigger_metrics.txt")
LAST_TEST_NAME = None

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
    # print(f"[RECV] {channel_name} | SeqNo={seqno} | Data='{payload}'", flush=True)

async def check_metrics_trigger():
    """Periodically check if metrics should be saved"""
    global LAST_TEST_NAME
    recv_api = None
    last_check_time = 0
    
    while True:
        await asyncio.sleep(0.5)

        # Always fetch the latest API; switch when it changes
        latest_api = Receiver.get_latest_api()
        if latest_api is None:
            continue
        if recv_api is not latest_api:
            recv_api = latest_api
            # Optional: reset metrics when a new connection arrives
            recv_api.reset_metrics()

        if os.path.exists(METRICS_TRIGGER_FILE):
            # Read the test label from the trigger file
            try:
                with open(METRICS_TRIGGER_FILE, "r") as f:
                    test_label = f.read().strip()
                
                # Only process if this is a new test (avoid duplicate processing)
                if test_label != LAST_TEST_NAME:
                    LAST_TEST_NAME = test_label
                    print(f"[ReceiverRunner] Saving metrics for test: {test_label}", flush=True)
                    
                    recv_api.compute_metrics(label=f"Receiver-{test_label}")
                    print(f"[ReceiverRunner] Metrics saved to results/Receiver-{test_label}.json", flush=True)
    
                    # Reset metrics to avoid accumulation into next test
                    recv_api.reset_metrics()
                    
                    # Remove trigger file after processing
                    try:
                        os.remove(METRICS_TRIGGER_FILE)
                    except:
                        pass
            except Exception as e:
                print(f"[ReceiverRunner] Error processing metrics trigger: {e}", flush=True)

async def main():
    print(f"[ReceiverRunner] Starting receiver on 0.0.0.0:4433", flush=True)
    
    # Set up signal handler for graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        print("\n[ReceiverRunner] Shutdown signal received, computing final metrics...", flush=True)
        shutdown_event.set()
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    server = None
    metrics_task = None
    
    try:
        server = await Receiver.create_receiver(local_port=4433, callback=handle_packet)
        
        # Start metrics trigger checker in background
        metrics_task = asyncio.create_task(check_metrics_trigger())
        
        await shutdown_event.wait()
        
    finally:
        print("[ReceiverRunner] Shutting down...", flush=True)
        
        # Cancel metrics task
        if metrics_task:
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass
        
        # Close the server
        if server:
            server.close()
            await server.wait_closed()
        
        # Compute and print final metrics before shutdown
        recv_api = Receiver.get_latest_api()
        if recv_api:
            recv_api.compute_metrics(label="Receiver-final")
        print("[ReceiverRunner] Shutdown complete", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
