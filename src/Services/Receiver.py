import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetProtocol, GameNetAPI
import os

LATEST_API = None

def get_latest_api() -> GameNetAPI:
    """Return the latest GameNetAPI instance created by the server (if any)."""
    return LATEST_API

async def create_receiver(local_port=4433, callback=None):
    """
    Create a GameNetAPI receiver (server).
    
    :param local_port: Port to listen on
    :param callback: Function to call when packets are received
    """
    configuration = QuicConfiguration(is_client=False)
    
    # Get absolute path to certificates relative to this file
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cert_dir_abs = os.path.join(root_dir, "certs")
    cert_path = os.path.join(cert_dir_abs, "cert.pem")
    key_path = os.path.join(cert_dir_abs, "key.pem") 
    configuration.load_cert_chain(cert_path, key_path)
    configuration.max_datagram_frame_size = 65535  # or some appropriate size


    def create_protocol(*args, **kwargs):
        """Factory to create protocol instances"""
        # Create the QUIC protocol with event handling
        protocol = GameNetProtocol(*args, **kwargs)
        
        # Attach GameNetAPI to it
        protocol.api = GameNetAPI(protocol)
        
        # Expose latest API for metrics access
        global LATEST_API
        LATEST_API = protocol.api

        # Set the callback if provided
        if callback:
            protocol.api.set_receive_callback(callback)
        return protocol

    print(f"[Receiver] Listening on 0.0.0.0:{local_port}")
    
    # Start the server
    return await serve(
        "0.0.0.0",
        local_port,
        configuration=configuration,
        create_protocol=create_protocol
    )