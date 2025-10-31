import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetProtocol, GameNetAPI


async def create_receiver(local_port=4433, callback=None):
    """
    Create a GameNetAPI receiver (server).
    
    :param local_port: Port to listen on
    :param callback: Function to call when packets are received
    """
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain("cert.pem", "key.pem")
    configuration.max_datagram_frame_size = 65535  # or some appropriate size


    def create_protocol(*args, **kwargs):
        """Factory to create protocol instances"""
        # Create the QUIC protocol with event handling
        protocol = GameNetProtocol(*args, **kwargs)
        
        # Attach GameNetAPI to it
        protocol.api = GameNetAPI(protocol)
        
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