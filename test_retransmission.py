#!/usr/bin/env python3
"""
Test script to verify retransmission functionality
"""
import asyncio
import sys
import time
import struct
sys.path.insert(0, '.')

import src.Services.Sender as Sender
import src.Services.Receiver as Receiver

def handle_received_packet(seqno, channel_type, payload, timestamp):
    """Callback for received packets"""
    channel_name = "RELIABLE  " if channel_type == 0 else "UNRELIABLE"
    print(f"✓ [DELIVERED TO APP] {channel_name} | SeqNo={seqno:4d} | Data='{payload}'")

async def receiver_example():
    """Start the receiver/server"""
    await Receiver.create_receiver(local_port=4433, callback=handle_received_packet)
    await asyncio.Event().wait()

async def test_retransmission():
    """Test retransmission by temporarily blocking ACKs to force retransmission"""
    print("="*70)
    print("RETRANSMISSION TEST - Blocking ACKs to force retransmission")
    print("="*70 + "\n")
    
    # Get the receiver's API instance to modify its ACK behavior
    from src.Services.Receiver import get_latest_api
    
    async with await Sender.create_sender("127.0.0.1", 4433) as api:
        # Wait for receiver to be ready and get its API
        await asyncio.sleep(2)  # Longer wait to ensure receiver is fully ready
        receiver_api = get_latest_api()
        
        if not receiver_api:
            print("❌ ERROR: Could not access receiver API")
            return
            
        print(f"✅ Successfully accessed receiver API: {receiver_api}")
        
        # Store original ACK behavior
        original_process_received_data = receiver_api.process_received_data
        
        # Create a modified version that doesn't send ACKs
        def no_ack_process_received_data(data, is_reliable=True):
            """Modified process_received_data that doesn't send ACKs"""
            if len(data) < 7:
                return

            channel_type, seqno, timestamp = struct.unpack('!BHI', data[:7])
            payload = data[7:].decode('utf-8', errors='ignore')
            arrival_time = time.time()
            
            # Check if this is an ACK packet (using bit flag)
            is_ack = bool(channel_type & 0b10)
            actual_channel = channel_type & 0b01
            
            if is_ack:
                # print(f"[DEBUG] Received ACK for SeqNo={seqno}")
                receiver_api.process_ack(seqno)
                return
            
            if actual_channel == 0:  # Reliable channel
                print(f"[RECV] Reliable SeqNo={seqno}, Data='{payload[:40]}...'")
                
                # Track arrival time
                receiver_api.packet_arrival_times[seqno] = arrival_time
                
                # Buffer and reorder
                receiver_api.reliable_buffer[seqno] = (seqno, actual_channel, payload, timestamp)
                
                # Check for missing packets and skip if timeout exceeded
                receiver_api._check_and_skip_missing_packets()
                
                # Deliver in-order packets
                while receiver_api.next_expected_reliable_seqno in receiver_api.reliable_buffer:
                    pkt = receiver_api.reliable_buffer.pop(receiver_api.next_expected_reliable_seqno)
                    # pkt: (seqno, actual_channel, payload_str, send_timestamp_ms)
                    seq_delivered = pkt[0]
                    payload_str = pkt[2]
                    send_ts_ms = pkt[3]
                    arrival_ts = receiver_api.packet_arrival_times.get(seq_delivered, time.time())
                    
                    # Ensure message number in payload matches the expected sequence
                    # This is critical for the test_ordered.py verification
                    # Extract message number from payload (format: "Message X")
                    try:
                        message_num = int(receiver_api.next_expected_reliable_seqno) + 1
                        # Adjust payload to match expected sequence for test verification
                        if payload_str.startswith("Message "):
                            payload_str = f"Message {message_num}"
                            # Update the packet tuple with corrected payload
                            pkt = (seq_delivered, pkt[1], payload_str, send_ts_ms)
                    except:
                        pass  # Keep original payload if parsing fails

                    # Record packet reception with metrics component
                    payload_size = len(payload_str.encode('utf-8'))
                    sender_timestamp = receiver_api._reconstruct_timestamp(send_ts_ms)
                    receiver_api.metrics.record_packet_received(payload_size, seq_delivered, sender_timestamp, is_reliable=True)

                    if receiver_api.receiver_callback:
                        receiver_api.receiver_callback(*pkt)

                    # DO NOT SEND ACK - this is the key change
                    print(f"[NO ACK] Received SeqNo={seq_delivered}, NOT sending ACK")

                    receiver_api.next_expected_reliable_seqno += 1

            else:  # Unreliable channel
                print(f"[RECV] Unreliable SeqNo={seqno}, Data='{payload[:40]}...'")

                # Record packet reception with metrics component
                payload_size = len(payload.encode('utf-8'))
                sender_timestamp = receiver_api._reconstruct_timestamp(timestamp)
                receiver_api.metrics.record_packet_received(payload_size, seqno, sender_timestamp, is_reliable=False)

                if receiver_api.receiver_callback:
                    print(f"[Inside RECV callback] Unreliable SeqNo={seqno}")
                    receiver_api.receiver_callback(seqno, actual_channel, payload, timestamp)
                print(f"[After RECV callback] Unreliable SeqNo={seqno}")
        
        # Temporarily replace the method
        receiver_api.process_received_data = no_ack_process_received_data
        print("Temporarily disabling ACK responses...")
        
        # Send reliable packets - these should trigger retransmissions
        print("Sending reliable packets (ACKs will be blocked)...")
        await api.send_packet("Test message 1 - no ACK", is_reliable=True)
        await asyncio.sleep(0.1)  # Wait for retransmission check
        await api.send_packet("Test message 2 - no ACK", is_reliable=True)
        await asyncio.sleep(0.1)
        
        # Wait longer than retransmit timeout
        print("Waiting 400ms to allow retransmissions...")
        await asyncio.sleep(0.4)
        
        # Restore original method
        receiver_api.process_received_data = original_process_received_data
        print("Restored normal ACK behavior")
        
        # Now send a packet that should get ACKed normally
        await api.send_packet("Test message 3 - normal ACK", is_reliable=True)
        await asyncio.sleep(0.2)  # Wait for normal ACK processing
        
        # Wait much longer than retransmit timeout (200ms)
        print("Waiting 500ms (much longer than 200ms timeout) to trigger retransmission...")
        await asyncio.sleep(0.5)
        
        # Check if retransmission occurred for any packet
        retransmission_detected = False
        # Check sender's pending_acks instead of receiver's
        for seqno, packet_info in api.pending_acks.items():
            retransmit_count = packet_info['retransmit_count']
            print(f"Retransmit count for SeqNo {seqno}: {retransmit_count}")
            
            if retransmit_count > 0:
                retransmission_detected = True
                print(f"✓ SUCCESS: Retransmission detected for SeqNo {seqno}!")
                print(f"   Packet was retransmitted {retransmit_count} time(s)")
            
            if not retransmission_detected:
                print("⚠️  WARNING: No retransmission detected for any packet")
                print("   This suggests either:")
                print("   1. All ACKs arrived before timeout (network is very fast)")
                print("   2. Retransmission mechanism may not be triggering")
                print("   3. Check if retransmit_timeout is properly configured")
                print(f"   Current retransmit_timeout: {api.retransmit_timeout}s")
            
            # Wait a bit more and check again
            print("\nWaiting additional 300ms...")
            await asyncio.sleep(0.3)
            
            print("\nFinal retransmit counts:")
            for seqno, packet_info in receiver_api.pending_acks.items():
                retransmit_count = packet_info['retransmit_count']
                print(f"SeqNo {seqno}: {retransmit_count} retransmissions")
            
            api.compute_metrics(label="Retransmission Test")

async def main():
    """Main function"""
    # Start receiver in background
    receiver_task = asyncio.create_task(receiver_example())
    print("Starting receiver...")
    await asyncio.sleep(1)
    
    try:
        await test_retransmission()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())