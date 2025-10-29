import src.Services.Sender as Sender
import src.Services.Reciever as Reciever

# For demonstration, when we finish building the sender, receiver, and GameNetAPI modules.

# Sender application
async def sender_example():
    api = await Sender.create_sender("127.0.0.1", 4433)
    await api.send_packet("Critical update", is_reliable=True)
    await api.send_packet("Position update", is_reliable=False)

# Receiver application
def handle_received_packet(seqno, channel_type, payload, timestamp):
    print(f"Received: SeqNo={seqno}, Type={channel_type}, Data={payload}, Time={timestamp}")

async def receiver_example():
    server = await Reciever.create_receiver(local_port=4433, callback=handle_received_packet)
    # Server runs until stopped

