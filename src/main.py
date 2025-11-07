import asyncio
import src.Services.Sender as Sender
import src.Services.Receiver as Receiver


def handle_received_packet(seqno, channel_type, payload, timestamp):
    """Callback for received packets"""
    channel_name = "RELIABLE  " if channel_type == 0 else "UNRELIABLE"
    print(f"[Receiver] {channel_name} | SeqNo={seqno:4d} | Data='{payload[:50]}'")


async def receiver_example():
    """Start the receiver/server"""
    await Receiver.create_receiver(local_port=4433, callback=handle_received_packet)
    # Keep running indefinitely
    await asyncio.Event().wait()


async def sender_example():
    """Send test packets"""
    print("\n[Sender] Starting to send packets...\n")
    
    # Use context manager to keep connection alive
    async with await Sender.create_sender("127.0.0.1", 4433) as api:
        
        # Send some reliable packets
        print("--- Sending Reliable Packets ---")
        for i in range(5):
            await api.send_packet(f"Reliable message {i+1}", is_reliable=True)
            await asyncio.sleep(0.1)  # Small delay between packets
        
        # Wait for ACKs
        await asyncio.sleep(0.5)
        
        # Send some unreliable packets
        print("\n--- Sending Unreliable Packets ---")
        for i in range(5):
            await api.send_packet(f"Unreliable message {i+1}", is_reliable=False)
            await asyncio.sleep(0.1)
        
        # Wait for packets to be processed
        print("\n[Sender] Waiting for final packets to be processed...")
        await asyncio.sleep(2)

        # Show metrics from both perspectives
        print("\n" + "="*70)
        print("SENDER-SIDE METRICS")
        print("="*70)
        api.compute_metrics(label="Sender-side")
        
        print("\n" + "="*70)
        print("RECEIVER-SIDE METRICS")
        print("="*70)
        recv_api = Receiver.get_latest_api()
        if recv_api:
            recv_api.compute_metrics(label="Receiver-side")
        else:
            print("[WARN] Receiver API not available; cannot print receiver-side metrics.")


async def main():
    """Main function"""
    print("="*70)
    print("CS3103 Assignment 4 - GameNetAPI Test")
    print("="*70)
    
    # Start receiver in background
    receiver_task = asyncio.create_task(receiver_example())
    
    # Give receiver time to start
    print("\n[Main] Starting receiver...")
    await asyncio.sleep(1)
    
    try:
        # Run sender
        await sender_example()
        
    except KeyboardInterrupt:
        print("\n[Main] Test interrupted by user")
    except Exception as e:
        print(f"\n[Main] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up receiver
        print("\n[Main] Cleaning up...")
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass
        
        print("\n" + "="*70)
        print("Test Complete!")
        print("="*70)


if __name__ == "__main__":
    asyncio.run(main())