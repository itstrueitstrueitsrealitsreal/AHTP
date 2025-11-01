"""
Driver script to test message ordering correctness
Sends multiple messages and verifies they are received in order
"""
import asyncio
import sys
import argparse
sys.path.insert(0, '.')
import src.Services.Sender as Sender
import os
import json

LOG_FILE = os.path.join(os.getcwd(), "receiver_log.jsonl") 
PROJECT_ROOT = os.getcwd()
VENV_PYTHON = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
RECEIVER_SCRIPT = os.path.join("src", "receiver_runner.py")


class MessageChecker:
    """Tracks received messages to verify ordering"""
    def __init__(self):
        self.received_messages = []
        self.test_messages = []  # Track messages per test
    
    def handle_received_packet(self, seqno, channel_type, payload, timestamp):
        """Callback for received packets"""
        self.received_messages.append({
            'seqno': seqno,
            'channel_type': channel_type,
            'payload': payload,
            'timestamp': timestamp
        })
        channel_name = "RELIABLE" if channel_type == 0 else "UNRELIABLE"
        print(f"[RECV] {channel_name} | SeqNo={seqno:4d} | Data='{payload}'", flush=True)
    
    def get_received_messages(self):
        """Get all received messages"""
        return self.received_messages.copy()
    
    def clear(self):
        """Clear received messages"""
        self.received_messages.clear()

async def send_test_messages(num_messages=10, reliability_type='reliable', delay=0.1, host="127.0.0.1", port=4433):
    """Send test messages"""
    print(f"\n{'='*70}")
    print(f"Sending {num_messages} {reliability_type.upper()} messages")
    print(f"{'='*70}\n")
    
    is_reliable = (reliability_type == 'reliable')
    
    async with await Sender.create_sender(host, port) as api:
        # Send messages
        for i in range(1, num_messages + 1):
            message = f"Message {i}"
            await api.send_packet(message, is_reliable=is_reliable)
            print(f"[SEND] Message {i}: '{message}'")
            if delay > 0:
                await asyncio.sleep(delay)
        
        # Wait for all messages to be processed
        print(f"\nWaiting for all messages to be delivered...")
        await asyncio.sleep(1.0)  # Allow time for delivery
        api.compute_metrics(label="Sender-side")

def check_message_ordering(received_messages, is_reliable=True):
    """Verify that messages are received in order"""
    if not received_messages:
        return False, "No messages received"
    
    # Filter by channel type
    filtered_messages = [msg for msg in received_messages if 
                        msg['channel_type'] == (0 if is_reliable else 1)]
    
    if not filtered_messages:
        return False, "No messages of specified type received"
    
    # Check ordering by sequence number
    seqnos = [msg['seqno'] for msg in filtered_messages]
    expected_seqnos = list(range(seqnos[0], seqnos[0] + len(seqnos)))
    
    if seqnos != expected_seqnos:
        return False, f"Out of order! Expected: {expected_seqnos}, Got: {seqnos}"
    
    # Check ordering by payload content (additional verification)
    for i, msg in enumerate(filtered_messages):
        expected_payload = f"Message {i + 1}"
        if msg['payload'] != expected_payload:
            return False, f"Payload mismatch at position {i}: expected '{expected_payload}', got '{msg['payload']}'"
    
    return True, "Messages received in correct order"


async def run_test(test_name, num_messages, reliability_type, delay=0.1, checker=None, host="127.0.0.1", port=4433):
    """Run a single test"""
    print(f"\n{'#'*70}")
    print(f"TEST: {test_name}")
    print(f"{'#'*70}")
    
    # Clear messages from previous test
    if checker:
        num_before = len(checker.get_received_messages())
    else:
        checker = MessageChecker()
        num_before = 0
    
    try:
        # Send messages
        await send_test_messages(num_messages, reliability_type, delay, host, port)
        
        # Wait a bit more for any late messages
        await asyncio.sleep(0.5)
        
        # Get received messages
        # received = checker.get_received_messages()
        try:
            with open(LOG_FILE, "r") as f:
                all_lines = [json.loads(line) for line in f]
        except FileNotFoundError:
            all_lines = []

        test_received = [msg for msg in all_lines if msg["channel_type"] == (0 if reliability_type == "reliable" else 1)]
        
        is_reliable = (reliability_type == 'reliable')
        is_ordered, message = check_message_ordering(test_received, is_reliable)
        
        # Print results
        print(f"{'='*70}")
        print(f"TEST RESULTS: {test_name}")
        print(f"{'='*70}")
        print(f"Messages sent:     {num_messages}")
        print(f"Messages received: {len(test_received)}")
        
        if is_reliable:
            filtered_count = len([msg for msg in test_received if msg['channel_type'] == 0])
            print(f"Reliable received: {filtered_count}")
        else:
            filtered_count = len([msg for msg in test_received if msg['channel_type'] == 1])
            print(f"Unreliable received: {filtered_count}")
        
        print(f"\nOrdering check: {'✓ PASS' if is_ordered else '✗ FAIL'}")
        print(f"Result: {message}")
        print(f"{'='*70}\n")
        
        return is_ordered
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        try:
            open(LOG_FILE, "w").close()  # truncates file
            print(f"[Cleanup] Cleared receiver log: {LOG_FILE}")
        except Exception as e:
            print(f"[Cleanup] Failed to clear log file: {e}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Test message ordering correctness for GameNetAPI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings (localhost:4433)
  python3 src/test_ordered.py

  # Custom port
  python3 src/test_ordered.py --port 8080

  # Custom host and port
  python3 src/test_ordered.py --host 192.168.1.100 --port 9000
        """
    )
    
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='Host address for sender to connect to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=4433,
                        help='Port number (default: 4433)')
    parser.add_argument('--netem', type=int, default=0,
                        help='1=Netem, 0=Non-netem')
    
    return parser.parse_args()


async def main():
    """Main function - run all tests"""
    args = parse_args()
    
    host = args.host
    port = args.port
    netem = args.netem
    
    print("="*70)
    print("CS3103 Assignment 4 - Message Ordering Test Suite")
    print("="*70)
    print(f"Configuration: host={host}, port={port}")
    print("="*70)
    
    tests = []
    
    # Create shared checker
    checker = MessageChecker()
    
    # Start receiver subprocess inside receiver namespace
    print(f"\n[Main] Launching receiver in 'receiver' namespace...")
    cmd = []

    if netem == 1:
        # run inside receiver namespace
        cmd = [
            "sudo", "ip", "netns", "exec", "receiver",
            VENV_PYTHON,
            RECEIVER_SCRIPT,
        ]
    else:
        # run directly (no netns)
        cmd = [
            VENV_PYTHON,
            RECEIVER_SCRIPT,
        ]

    receiver_process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    await asyncio.sleep(2)  # give receiver time to start

    
    try:
        # Test 1: Small number of reliable messages
        print("\n>>> Running Test 1: Small batch of reliable messages")
        result1 = await run_test(
            "Small reliable batch",
            num_messages=5,
            reliability_type='reliable',
            delay=0.1,
            checker=checker,
            host=host,
            port=port
        )
        tests.append(("Test 1: Small reliable batch", result1))
        await asyncio.sleep(0.5)
        
        # Test 2: Larger number of reliable messages
        print("\n>>> Running Test 2: Larger batch of reliable messages")
        result2 = await run_test(
            "Large reliable batch",
            num_messages=20,
            reliability_type='reliable',
            delay=0.05,
            checker=checker,
            host=host,
            port=port
        )
        tests.append(("Test 2: Large reliable batch", result2))
        await asyncio.sleep(0.5)
        
        # Test 3: Rapid reliable messages (stress test)
        print("\n>>> Running Test 3: Rapid reliable messages")
        result3 = await run_test(
            "Rapid reliable messages",
            num_messages=15,
            reliability_type='reliable',
            delay=0.01,
            checker=checker,
            host=host,
            port=port
        )
        tests.append(("Test 3: Rapid reliable messages", result3))
        await asyncio.sleep(0.5)
        
        # Test 4: Unreliable messages
        print("\n>>> Running Test 4: Unreliable messages")
        result4 = await run_test(
            "Unreliable messages",
            num_messages=10,
            reliability_type='unreliable',
            delay=0.1,
            checker=checker,
            host=host,
            port=port
        )
        tests.append(("Test 4: Unreliable messages", result4))
        
    finally:
        print("\n[Main] Stopping receiver...")
        try:
            receiver_process.terminate()
            await receiver_process.wait()
        except ProcessLookupError:
            pass

    # Print summary
    print(f"\n{'='*70}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*70}")
    
    all_passed = True
    for test_name, passed in tests:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print(f"{'='*70}")
    if all_passed:
        print("OVERALL: ✓ ALL TESTS PASSED")
    else:
        print("OVERALL: ✗ SOME TESTS FAILED")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
