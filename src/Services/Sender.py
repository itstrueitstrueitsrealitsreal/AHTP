# module-level imports
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from Objects.GameNetAPI import GameNetAPI
import os
import ssl
import time
import struct
import asyncio
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import QuicEvent, StreamDataReceived, DatagramFrameReceived


# this is a sample i (ethan) asked ai to generate, see src/Objects/GameNetAPI.py, esp line 5 and 6

class GameNetClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = None
        self.stream_buffers = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        # Initialize GameNetAPI when connection is established
        if self.api is None:
            self.api = GameNetAPI(self)
        if isinstance(event, StreamDataReceived):
            buf = self.stream_buffers.get(event.stream_id, b"") + event.data
            self.stream_buffers[event.stream_id] = buf
            if event.end_stream:
                full = self.stream_buffers.pop(event.stream_id, b"")
                # ACKs and control messages will be parsed by GameNetAPI
                self.api.process_received_data(full, is_reliable=True)
        elif isinstance(event, DatagramFrameReceived):
            self.api.process_received_data(event.data, is_reliable=False)

async def create_sender(dest_ip="127.0.0.1", dest_port=4433, trust_server_cert=False):
    configuration = QuicConfiguration(is_client=True)
    configuration.alpn_protocols = ["hq-29"]
    configuration.server_name = "localhost"
    configuration.max_datagram_frame_size = 65536  # enable QUIC datagrams on the client

    if trust_server_cert:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cert_path = os.path.join(root_dir, "certs", "cert.pem")
        if os.path.exists(cert_path):
            configuration.verify_mode = ssl.CERT_REQUIRED
            configuration.load_verify_locations(cafile=cert_path)
            print(f"[Sender] Trusting server certificate at {cert_path}")
        else:
            configuration.verify_mode = ssl.CERT_NONE
            print("[Sender] Server cert not found, disabling verification for testing.")
    else:
        configuration.verify_mode = ssl.CERT_NONE

    def create_protocol(*args, **kwargs):
        return GameNetClientProtocol(*args, **kwargs)

    cm = connect(dest_ip, dest_port, configuration=configuration, create_protocol=create_protocol)
    protocol = await cm.__aenter__()

    # Wait for handshake to complete and for datagram negotiation
    for _ in range(20):  # up to ~1s
        if getattr(protocol._quic, "datagram_supported", False):
            break
        await asyncio.sleep(0.05)
    print(f"[Sender] Datagrams negotiated: {getattr(protocol._quic, 'datagram_supported', False)}")

    # Return the API instance attached to the protocol
    api = protocol.api
    return api
