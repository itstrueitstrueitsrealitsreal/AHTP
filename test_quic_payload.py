#!/usr/bin/env python3
"""
Test script to verify QUIC transmission with payload using unreliable sender.
This test checks if payloads are properly delivered through QUIC DATAGRAM frames.
"""

import asyncio
import time
from src.Objects.GameNetAPI import GameNetAPI
from src.Services.Sender import Sender
from src.Services.Receiver import Receiver

async def test_quic_payload_transmission():
    """Test QUIC payload transmission with unreliable sender"""
    
    # Initialize sender and receiver
    sender = Sender()
    receiver = Receiver()
    
    # Start both services
    await sender.start()
    await receiver.start()
    
    # Test payloads of different sizes
    test_payloads = [
        b"Hello World",  # Small payload
        b"A" * 512,      # Medium payload
        b"B" * 1200,     # Large payload (near typical MTU)
        b"Test payload with special chars!@#$%^&*()"
    ]
    
    received_payloads = []
    
    # Callback to capture received payloads
    def payload_received_callback(payload):
        print(f"Received payload: {payload[:50]}{'...' if len(payload) > 50 else ''}")
        received_payloads.append(payload)
    
    # Set up receiver callback
    receiver.set_payload_callback(payload_received_callback)
    
    # Send test payloads using unreliable channel
    print("Sending test payloads via unreliable channel...")
    for i, payload in enumerate(test_payloads):
        print(f"Sending payload {i+1}: {payload[:30]}{'...' if len(payload) > 30 else ''}")
        await sender.send_unreliable(payload)
        await asyncio.sleep(0.1)  # Small delay between sends
    
    # Wait for payloads to be received
    print("Waiting for payload reception...")
    await asyncio.sleep(2)  # Allow time for transmission
    
    # Verify received payloads
    print(f"\nTest Results:")
    print(f"Sent {len(test_payloads)} payloads")
    print(f"Received {len(received_payloads)} payloads")
    
    # Check for payload integrity
    successful_transmissions = 0
    for sent_payload in test_payloads:
        if sent_payload in received_payloads:
            successful_transmissions += 1
            print(f"✓ Payload delivered successfully: {sent_payload[:30]}{'...' if len(sent_payload) > 30 else ''}")
        else:
            print(f"✗ Payload not received: {sent_payload[:30]}{'...' if len(sent_payload) > 30 else ''}")
    
    # Check for any issues
    print(f"\nSuccess rate: {successful_transmissions}/{len(test_payloads)} ({successful_transmissions/len(test_payloads)*100:.1f}%)")
    
    if successful_transmissions == len(test_payloads):
        print("✅ All payloads transmitted successfully!")
    else:
        print("❌ Some payloads failed to transmit")
        
        # Check if we received any unexpected payloads
        unexpected_payloads = [p for p in received_payloads if p not in test_payloads]
        if unexpected_payloads:
            print(f"Received {len(unexpected_payloads)} unexpected payloads:")
            for payload in unexpected_payloads:
                print(f"  - {payload}")
    
    # Clean up
    await sender.stop()
    await receiver.stop()
    
    return successful_transmissions == len(test_payloads)

async def test_payload_fragmentation():
    """Test if large payloads are properly handled (fragmentation/reassembly)"""
    
    sender = Sender()
    receiver = Receiver()
    
    await sender.start()
    await receiver.start()
    
    # Very large payload to test fragmentation
    large_payload = b"X" * 5000  # Larger than typical QUIC packet size
    
    received_payload = None
    
    def capture_payload(payload):
        nonlocal received_payload
        received_payload = payload
        print(f"Received large payload of size: {len(payload)} bytes")
    
    receiver.set_payload_callback(capture_payload)
    
    print(f"Sending large payload ({len(large_payload)} bytes)...")
    await sender.send_unreliable(large_payload)
    
    # Wait longer for large payload transmission
    await asyncio.sleep(3)
    
    success = received_payload == large_payload
    
    if success:
        print("✅ Large payload transmitted successfully!")
    else:
        if received_payload:
            print(f"❌ Payload mismatch. Sent: {len(large_payload)} bytes, Received: {len(received_payload)} bytes")
        else:
            print("❌ Large payload not received")
    
    await sender.stop()
    await receiver.stop()
    
    return success

if __name__ == "__main__":
    print("Testing QUIC payload transmission with unreliable sender")
    print("=" * 60)
    
    # Run basic payload test
    print("\n1. Basic payload transmission test:")
    basic_success = asyncio.run(test_quic_payload_transmission())
    
    print("\n" + "=" * 60)
    
    # Run fragmentation test
    print("\n2. Large payload fragmentation test:")
    fragmentation_success = asyncio.run(test_payload_fragmentation())
    
    print("\n" + "=" * 60)
    print("\nFinal Results:")
    print(f"Basic transmission: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"Fragmentation test: {'✅ PASS' if fragmentation_success else '❌ FAIL'}")
    
    if basic_success and fragmentation_success:
        print("\n🎉 All tests passed! QUIC payload transmission is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check QUIC configuration and network conditions.")