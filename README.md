# AHTP

## How to run:
1. Create virtual environment named 'venv'
1. `pip install -r requirements.txt`
1. `python scripts/generate_certs.py`
1. `make netem`

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