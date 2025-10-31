# module-level imports
import asyncio
import os
import importlib.util
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, DatagramFrameReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol
from Objects.GameNetAPI import GameNetAPI

# this is a sample i (ethan) asked ai to generate, see src/Objects/GameNetAPI.py, esp line 5 and 6

def load_tls_certificates(cert_dir="certs"):
    """
    Load TLS certificates for QUIC server.
    If missing, auto-generate using scripts/generate_certs.py.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cert_dir_abs = os.path.join(root_dir, cert_dir)
    cert_path = os.path.join(cert_dir_abs, "cert.pem")
    key_path = os.path.join(cert_dir_abs, "key.pem")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        generator_path = os.path.join(root_dir, "scripts", "generate_certs.py")
        if os.path.exists(generator_path):
            print("TLS certs not found, generating via scripts/generate_certs.py...")
            spec = importlib.util.spec_from_file_location("generate_certs", generator_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.generate_self_signed_cert(hostname="localhost", cert_dir="certs", force=False)

        if not (os.path.exists(cert_path) and os.path.exists(key_path)):
            raise FileNotFoundError(
                f"TLS certificates not found in {cert_dir_abs}/. "
                "Run 'python scripts/generate_certs.py' to create them."
            )

    return cert_path, key_path

class GameNetServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = None
        self.callback = None
    def quic_event_received(self, event: QuicEvent) -> None:
        """Handle QUIC events (stream data, datagrams, etc.)"""
        
        # Initialize GameNetAPI when connection is established
        if self.api is None:
            self.api = GameNetAPI(self)
            if self.callback:
                self.api.set_receive_callback(self.callback)
        
        if isinstance(event, StreamDataReceived):
            print(f"[Receiver] Stream {event.stream_id}: +{len(event.data)} bytes")
            self.api.process_received_data(event.data, is_reliable=True)
        elif isinstance(event, DatagramFrameReceived):
            print(f"[Receiver] Received unreliable datagram: {len(event.data)} bytes")
            self.api.process_received_data(event.data, is_reliable=False)

async def create_receiver(local_port=4433, callback=None, cert_dir="certs"):
    """
    Create a GameNetAPI receiver (server).
    """
    configuration = QuicConfiguration(is_client=False)
    configuration.alpn_protocols = ["hq-29"]
    configuration.max_datagram_frame_size = 65536  

    cert_path, key_path = load_tls_certificates(cert_dir)
    configuration.load_cert_chain(cert_path, key_path)
    print(f"Loaded TLS certificates from {os.path.dirname(cert_path)}/")

    def create_protocol(*args, **kwargs):
        protocol = GameNetServerProtocol(*args, **kwargs)
        protocol.callback = callback
        return protocol

    print(f"Starting QUIC server on port {local_port}...")
    server = await serve(
        "0.0.0.0",
        local_port,
        configuration=configuration,
        create_protocol=create_protocol
    )
    print(f"QUIC server listening on 0.0.0.0:{local_port}")
    return server