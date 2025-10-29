# AHTP

## Architecture breakdown:
Client/Server
         ↓
GameNetAPI
         ↓
QuicConnectionProtocol (asyncio wrapper, passed as a param into GameNetAPI from client/server bc protocol config different for sender and receiver)
         ↓
QuicConnection (core QUIC logic)
         ↓
UDP Socket (actual network transport)
         ↓
Network/Internet