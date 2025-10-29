import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetAPI

# this is a sample i (ethan) asked ai to generate, see src/Objects/GameNetAPI.py, esp line 5 and 6

async def create_receiver(local_port=4433, callback=None):
    """
    Create a GameNetAPI receiver (server).
    
    :param local_port: Port to listen on
    :param callback: Function to call when packets are received
    :return: Server task
    """
    configuration = QuicConfiguration(is_client=False)
    # You'll need to generate certificates for production use
    # For now, this is a placeholder - QUIC requires TLS
    
    async def handle_connection(protocol):
        api = GameNetAPI(protocol)
        if callback:
            api.set_receive_callback(callback)
        # Handle incoming events
        # This will need to be integrated with aioquic's event loop
    
    return await serve(
        "0.0.0.0",
        local_port,
        configuration=configuration,
        create_protocol=handle_connection
    )