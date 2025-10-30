import asyncio
from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from src.Objects.GameNetAPI import GameNetAPI


class GameServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = GameNetAPI(self)
        if callback:
            self.api.set_receive_callback(callback)

    def quic_event_received(self, event):
        # can be extended later for metrics or debug
        pass


async def create_receiver(local_port=4433, callback=None, configuration=None):
    if configuration is None:
        configuration = QuicConfiguration(is_client=False)
        configuration.load_cert_chain("cert.pem", "key.pem")

    print(f"[Receiver] Listening on port {local_port}")

    return await serve(
        "0.0.0.0",
        local_port,
        configuration=configuration,
        create_protocol=lambda *args, **kwargs: GameServerProtocol(*args, callback=callback, **kwargs)
    )
