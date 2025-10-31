"""
Simple diagnostic test to check packet flow
"""
import asyncio
import src.Services.Sender as Sender
import src.Services.Reciever as Reciever


def handle_received_packet(seqno, channel_type, payload, timestamp):
    """Callback for received packets"""
    channel_name = "RELIABLE  " if channel_type == 0 else "UNRELIABLE"
    print(f"✓ [DELIVERED TO APP] {channel_name} | SeqNo={seqno:4d} | Data='{payload}'")


async def receiver_example():
    """Start the receiver/server"""
    await Reciever.create_receiver(local_port=4433, callback=handle_received_packet)
    await asyncio.Event().wait()


async def sender_example():
    """Send test packets with diagnostics"""
    print("\n" + "="*70)
    print("DIAGNOSTIC TEST - Sending 3 reliable packets")
    print("="*70 + "\n")
    
    async with await Sender.create_sender("127.0.0.1", 4433) as api:
        
        # Send 3 reliable packets slowly
        for i in range(3):
            print(f"\n--- Sending packet {i+1} ---")
            await api.send_packet(f"Test message {i+1}", is_reliable=True)
            print(f"Waiting 1 second for ACK...")
            await asyncio.sleep(1)
        
        print("\n--- All packets sent, waiting 3 seconds for final ACKs ---")
        await asyncio.sleep(3)
        
        # Check results
        print("\n" + "="*70)
        print("DIAGNOSTIC RESULTS")
        print("="*70)
        print(f"Packets sent:     {api.total_sent}")
        print(f"ACKs received:    {len(api.acked_packets)}")
        print(f"Pending ACKs:     {len(api.pending_acks)}")
        print(f"Acked packet IDs: {sorted(api.acked_packets)}")
        print(f"Pending IDs:      {sorted(api.pending_acks.keys())}")
        
        if api.latency_records:
            avg_rtt = sum(api.latency_records) / len(api.latency_records) * 1000
            print(f"Average RTT:      {avg_rtt:.2f} ms")
        else:
            print("Average RTT:      No ACKs received!")
        
        print("="*70)
        
        if len(api.acked_packets) == 0:
            print("\n❌ PROBLEM: No ACKs received!")
            print("Possible causes:")
            print("1. Receiver not processing packets correctly")
            print("2. ACK packets not formatted correctly") 
            print("3. Sender not detecting ACK packets")
        elif len(api.acked_packets) < api.total_sent:
            print(f"\n⚠️  WARNING: Only {len(api.acked_packets)}/{api.total_sent} ACKs received")
        else:
            print("\n✓ SUCCESS: All packets acknowledged!")


async def main():
    """Main function"""
    print("="*70)
    print("CS3103 Assignment 4 - Diagnostic Test")
    print("="*70)
    
    # Start receiver
    receiver_task = asyncio.create_task(receiver_example())
    print("\n[Main] Starting receiver...")
    await asyncio.sleep(1)
    
    try:
        await sender_example()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[Main] Cleaning up...")
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())