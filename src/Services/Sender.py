from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetAPI


# this is a sample i (ethan) asked ai to generate, see src/Objects/GameNetAPI.py, esp line 5 and 6

async def create_sender(dest_ip="127.0.0.1", dest_port=4433):
    """
    Create a GameNetAPI sender (client).
    
    :param dest_ip: Destination IP address
    :param dest_port: Destination port
    :return: GameNetAPI instance
    """
    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = False  # Disable certificate verification for testing
    
    async with connect(dest_ip, dest_port, configuration=configuration) as protocol:
        api = GameNetAPI(protocol)
        return api
