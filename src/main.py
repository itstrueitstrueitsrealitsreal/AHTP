import Services.Sender as Sender
import Services.Reciever as Reciever
import argparse
import asyncio

# For demonstration, when we finish building the sender, receiver, and GameNetAPI modules.

# Sender application
async def sender_example(dest_ip="127.0.0.1", dest_port=4433, trust_server_cert=False):
    api = await Sender.create_sender(dest_ip, dest_port, trust_server_cert=trust_server_cert)

    # Repeated sends with randomized reliability
    import random, asyncio
    async def retransmit_loop():
        while True:
            await api.check_retransmissions()  
            await asyncio.sleep(0.05)

    # Start retransmission monitor in background
    asyncio.create_task(retransmit_loop())

    # Send 20 packets with random reliability
    for i in range(1, 21):
        is_reliable = random.choice([True, False])
        payload = f"Demo payload #{i} ({'reliable' if is_reliable else 'unreliable'})"
        print(f"[Sender] Sending #{i}: type={'reliable' if is_reliable else 'unreliable'}")
        await api.send_packet(payload, is_reliable=is_reliable)
        await asyncio.sleep(0.1)  # spacing for readability

# Receiver application
def handle_received_packet(seqno, channel_type, payload, timestamp):
    print(f"Received: SeqNo={seqno}, Type={channel_type}, Data={payload}, Time={timestamp}")

async def receiver_example(local_port=4433):
    server = await Reciever.create_receiver(local_port=local_port, callback=handle_received_packet)
    if server is None:
        print("Failed to start server - check TLS certificates")
        return
    print("Server is running. Press Ctrl+C to stop.")
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AHTP QUIC sender or receiver")
    parser.add_argument("--mode", choices=["receiver", "sender"], default="receiver", help="Which app to run")
    # Receiver args
    parser.add_argument("--local-port", type=int, default=4433, help="Receiver listening port")
    # Sender args
    parser.add_argument("--dest-ip", type=str, default="127.0.0.1", help="Sender destination IP")
    parser.add_argument("--dest-port", type=int, default=4433, help="Sender destination port")
    parser.add_argument("--trust-server-cert", action="store_true", help="Sender trusts certs/cert.pem")
    args = parser.parse_args()

    if args.mode == "receiver":
        asyncio.run(receiver_example(local_port=args.local_port))
    else:
        asyncio.run(sender_example(dest_ip=args.dest_ip, dest_port=args.dest_port, trust_server_cert=args.trust_server_cert))

