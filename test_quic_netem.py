#!/usr/bin/env python3
"""
Test script to verify QUIC transmission with payload using unreliable sender
under various network conditions using tc netem.
"""

import asyncio
import time
import subprocess
import os
from Objects.GameNetAPI import GameNetAPI
from Services.Sender import Sender
from Services.Receiver import Receiver

def setup_netem_impairment(delay="0ms", loss="0%", rate="1000mbit"):
    """Set up tc netem network impairments"""
    try:
        # Clear any existing qdisc
        subprocess.run(["sudo", "tc", "qdisc", "del", "dev", "lo", "root"], 
                      stderr=subprocess.DEVNULL)
        
        # Add netem qdisc with specified impairments
        cmd = ["sudo", "tc", "qdisc", "add", "dev", "lo", "root", "netem"]
        if delay != "0ms":
            cmd.extend(["delay", delay])
        if loss != "0%":
            cmd.extend(["loss", loss])
        if rate != "1000mbit":
            cmd.extend(["rate", rate])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: Failed to set netem impairment: {result.stderr}")
            return False
        
        print(f"Netem impairment set: delay={delay}, loss={loss}, rate={rate}")
        return True
        
    except Exception as e:
        print(f"Error setting up netem: {e}")
        return False

def cleanup_netem():
    """Clean up any netem impairments"""
    try:
        subprocess.run(["sudo", "tc", "qdisc", "del", "dev", "lo", "root"], 
                      stderr=subprocess.DEVNULL)
        print("Netem impairments cleaned up")
    except Exception as e:
        print(f"Error cleaning up netem: {e}")

async def test_quic_payload_transmission(netem_config=None):
    """Test QUIC payload transmission with unreliable sender under netem conditions"""
    
    # Set up network impairments if specified
    if netem_config:
        if not setup_netem_impairment(**netem_config):
            print("⚠️  Continuing test without netem impairments")
    
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
    
    # Wait for payloads to be received (longer wait for impaired networks)
    wait_time = 5 if netem_config else 2
    print(f"Waiting {wait_time} seconds for payload reception...")
    await asyncio.sleep(wait_time)
    
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
    success_rate = successful_transmissions / len(test_payloads) * 100
    print(f"\nSuccess rate: {successful_transmissions}/{len(test_payloads)} ({success_rate:.1f}%)")
    
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
    
    # Clean up netem if it was set up
    if netem_config:
        cleanup_netem()
    
    return successful_transmissions == len(test_payloads)

async def run_netem_tests():
    """Run tests under various network conditions"""
    
    netem_scenarios = [
        {"name": "No impairments", "config": None},
        {"name": "Low latency", "config": {"delay": "10ms", "loss": "0%", "rate": "100mbit"}},
        {"name": "Moderate latency", "config": {"delay": "50ms", "loss": "0%", "rate": "50mbit"}},
        {"name": "High latency", "config": {"delay": "100ms", "loss": "0%", "rate": "10mbit"}},
        {"name": "Packet loss (5%)", "config": {"delay": "20ms", "loss": "5%", "rate": "100mbit"}},
        {"name": "High loss (20%)", "config": {"delay": "20ms", "loss": "20%", "rate": "100mbit"}},
        {"name": "Low bandwidth", "config": {"delay": "10ms", "loss": "0%", "rate": "1mbit"}}
    ]
    
    results = {}
    
    for scenario in netem_scenarios:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*80}")
        
        # Run transmission test
        success = await test_quic_payload_transmission(scenario['config'])
        
        results[scenario['name']] = success
        
        print(f"\nResults for {scenario['name']}: {'✅ PASS' if success else '❌ FAIL'}")
        
        # Wait a moment between tests
        await asyncio.sleep(2)
    
    return results

if __name__ == "__main__":
    print("Testing QUIC payload transmission with unreliable sender under various network conditions")
    print("=" * 80)
    print("Note: This test requires sudo privileges for tc netem commands")
    
    # Ensure we start with clean network
    cleanup_netem()
    
    # Run all netem tests
    print("\nRunning comprehensive netem tests...")
    all_results = asyncio.run(run_netem_tests())
    
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    # Print summary
    total_scenarios = len(all_results)
    successful_scenarios = sum(1 for result in all_results.values() if result)
    
    print(f"Total scenarios tested: {total_scenarios}")
    print(f"Successful scenarios: {successful_scenarios}")
    print(f"Success rate: {successful_scenarios/total_scenarios*100:.1f}%")
    
    print("\nDetailed results:")
    for scenario, success in all_results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {scenario}: {status}")
    
    # Final cleanup
    cleanup_netem()
    
    if successful_scenarios == total_scenarios:
        print("\n🎉 All tests passed under all network conditions!")
    else:
        print("\n⚠️  Some tests failed under certain network conditions.")
        print("This is expected behavior - QUIC should handle network impairments gracefully.")
        print("The unreliable channel may drop packets under high loss conditions.")