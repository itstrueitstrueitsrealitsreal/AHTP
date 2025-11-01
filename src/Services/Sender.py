import asyncio
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetProtocol, GameNetAPI


async def create_sender(dest_ip="127.0.0.1", dest_port=4433):
    """
    Create a GameNetAPI sender (client).
    
    Returns a context manager that must be used with 'async with'
    
    Usage:
        async with await create_sender() as api:
            await api.send_packet("Hello", is_reliable=True)
    
    :param dest_ip: Destination IP address
    :param dest_port: Destination port
    :return: Context manager yielding GameNetAPI instance
    """
    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = False  # Disable certificate verification for testing
    configuration.max_datagram_frame_size = 65535  # or some appropriate size


    class SenderContext:
        """Context manager to keep connection alive"""
        def __init__(self, ip, port, config):
            self.ip = ip
            self.port = port
            self.config = config
            self.connection_context = None
            self.protocol = None
            self.api = None
            self.retransmit_task = None
        
        async def __aenter__(self):
            print(f"[Sender] Connecting to {self.ip}:{self.port}...")
            
            # Create connection context (this is what has __aenter__/__aexit__)
            self.connection_context = connect(
                self.ip, 
                self.port, 
                configuration=self.config,
                create_protocol=GameNetProtocol
            )
            
            # Enter the connection context to get the protocol
            self.protocol = await self.connection_context.__aenter__()
            
            # Create API with the protocol
            self.api = GameNetAPI(self.protocol)
            
            # Attach API to protocol so it can process received events
            self.protocol.api = self.api
            
            # Start retransmission loop in background
            self.retransmit_task = asyncio.create_task(self.api.start_retransmit_loop())
            
            print("[Sender] Connected successfully!")
            return self.api
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Cancel retransmit task
            if self.retransmit_task:
                self.retransmit_task.cancel()
                try:
                    await self.retransmit_task
                except asyncio.CancelledError:
                    pass
            
            # Close connection using the connection context
            if self.connection_context:
                await self.connection_context.__aexit__(exc_type, exc_val, exc_tb)
            
            print("[Sender] Connection closed")
    
    return SenderContext(dest_ip, dest_port, configuration)