import time
import struct

class GameNetAPI:
    # For sender: Pass the QuicConnectionProtocol from connect()
    # For receiver: Pass the QuicConnectionProtocol from the server handler
    def __init__(self, connection): # connection: QuicConnectionProtocol instance that you pass in from client/server instantation
        self.connection = connection

        # Separate sequence number for (un)reliable channel
        self.reliable_seqno = 0  
        self.unreliable_seqno = 0  
        
        # Sender-side: Track packets waiting for ACK
        self.pending_acks = {}
        
        # Receiver-side: Buffer and reordering
        self.reliable_buffer = {}  # {seqno: (seqno, channel_type, payload, timestamp)}
        self.packet_arrival_times = {}  # TODO use this for printing on client side: {seqno: arrival_time} 
        self.next_expected_reliable_seqno = 1  # Next expected seqno for reliable channel
        
        self.retransmit_timeout = 0.2  # 200ms default
        self.receiver_callback = None # for sender/recver side to set callback function to do printing of logs
        
        # Skipping lost packets after timeout
        self.missing_packet_timers = {}  # {seqno: first_time_noticed_missing} # if want to use for printing

    async def send_packet(self, data, is_reliable=True):
        # Use separate sequence numbers for each channel
        if is_reliable:
            self.reliable_seqno += 1
            seqno = self.reliable_seqno
            channel_type = 0
        else:
            self.unreliable_seqno += 1
            seqno = self.unreliable_seqno
            channel_type = 1

        # Construct packet with explicit header format
        # Header: | ChannelType (1B) | SeqNo (2B) | Timestamp (4B) | Payload |
        timestamp = int(time.time() * 1000)  # ms since epoch
        
        # Pack header
        header = struct.pack('!BHI', channel_type, seqno, timestamp) # Format exp: ! is network byte order, B is unsigned char (1 byte), H is unsigned short (2 bytes), I is unsigned int (4 bytes)
        payload = data.encode('utf-8') if isinstance(data, str) else data
        packet_data = header + payload
        
        if is_reliable:
            # Use QUIC stream for reliable delivery
            stream_id = 0  # Use stream 0 for reliable channel
            self.connection._quic.send_stream_data(stream_id, packet_data, end_stream=False)
            
            # Track for potential retransmission (though QUIC handles this alr, we track for monitoring)
            self.pending_acks[seqno] = {
                'packet_data': packet_data,
                'timestamp': time.time(),
                'retransmit_count': 0
            }
        else:
            # Use QUIC datagram for unreliable delivery
            self.connection._quic.send_datagram_frame(packet_data)
        
        # Transmit
        self.connection.transmit()
    
    def process_ack(self, seqno):
        if seqno in self.pending_acks:
            # Calculate RTT
            rtt = time.time() - self.pending_acks[seqno]['timestamp']
            del self.pending_acks[seqno]
            return rtt
        return None
    
    ## TODO QUIC already handles retransmissions at the transport layer, but part (e) asks us to implement (pls check if we need to go deeper or just tracking like this is enough)
    async def check_retransmissions(self): # Check for packets that need retransmission every now and then, (e.g., every 50ms)
        current_time = time.time()
        packets_to_retransmit = []
        
        # get packets that got no ACK
        for seqno, packet_info in list(self.pending_acks.items()):
            time_elapsed = current_time - packet_info['timestamp']
            
            if time_elapsed > self.retransmit_timeout:
                packets_to_retransmit.append((seqno, packet_info))
        
        # TODO Retransmit the packets (altho this handled by QUIC alr... so do we still do this?? we do it here as per requirement)
        for seqno, packet_info in packets_to_retransmit:
            stream_id = 0
            self.connection._quic.send_stream_data(stream_id, packet_info['packet_data'], end_stream=False)
            self.connection.transmit()
            
            # Update retransmission count and timestamp
            self.pending_acks[seqno]['retransmit_count'] += 1
            self.pending_acks[seqno]['timestamp'] = current_time
            
            print(f"[Retransmit] SeqNo={seqno}, Count={self.pending_acks[seqno]['retransmit_count']}")

    # TODO whoever doing sender/receiver side u can use this for logs in requirement (g)
    # EXAMPLE USAGE 
    # # Your custom handler function
    # def handle_received_packet(seqno, channel_type, payload, timestamp):
    #     print(f"Received: SeqNo={seqno}, Type={channel_type}, Data={payload}, Time={timestamp}")
    #     # Do whatever you want with the packet data

    # # Set the callback
    # receiver_api = GameNetAPI(connection)
    # receiver_api.set_receive_callback(handle_received_packet)

    # this is an observer pattern, decouples gamenetapi from app logic.
    def set_receive_callback(self, callback):
        """
        Set callback for received packets.
        
        :param callback: Function(seqno, channel_type, payload, timestamp) to call when packet received
        """
        self.receiver_callback = callback
    
    def process_received_data(self, data, is_reliable=True): # data is raw bytes received

        # Unpack header: | ChannelType (1B) | SeqNo (2B) | Timestamp (4B) | Payload |
        if len(data) < 7: # Invalid packet
            return          

        channel_type, seqno, timestamp = struct.unpack('!BHI', data[:7])
        payload = data[7:].decode('utf-8', errors='ignore')
        arrival_time = time.time()
        
        if channel_type == 0:  # Reliable channel
            # Track arrival time
            self.packet_arrival_times[seqno] = arrival_time
            
            # Buffer and reorder
            self.reliable_buffer[seqno] = (seqno, channel_type, payload, timestamp)
            
            # Check for missing packets and skip if timeout exceeded
            self._check_and_skip_missing_packets()
            
            # Deliver in-order packets 
            while self.next_expected_reliable_seqno in self.reliable_buffer:
                pkt = self.reliable_buffer.pop(self.next_expected_reliable_seqno)
                if self.receiver_callback:
                    self.receiver_callback(*pkt)
                self.next_expected_reliable_seqno += 1

        else:  # Unreliable channel
            # Deliver immediately, no ordering
            if self.receiver_callback:
                self.receiver_callback(seqno, channel_type, payload, timestamp)
    
    # Used by receiver side to skip lost packets after timeout
    def _check_and_skip_missing_packets(self): # Check for missing packets in the reliable buffer. If a packet is missing for more than 200ms, skip it and deliver subsequent packets.
        current_time = time.time()
        
        # Find all packets that have arrived
        arrived_seqnos = set(self.reliable_buffer.keys())
        
        # Check if we're waiting for any packets 
        if arrived_seqnos:
            max_arrived = max(arrived_seqnos)
            
            # Check for gaps between next_expected and max_arrived
            for expected_seqno in range(self.next_expected_reliable_seqno, max_arrived + 1):
                if expected_seqno not in arrived_seqnos:

                    # This packet missing
                    if expected_seqno not in self.missing_packet_timers:
                        # First time noticing this packet is missing
                        self.missing_packet_timers[expected_seqno] = current_time
                    else:
                        # Check if timeout exceeded
                        time_missing = current_time - self.missing_packet_timers[expected_seqno]
                        
                        if time_missing > self.retransmit_timeout:
                            # Skip this packet
                            print(f"[Skip] SeqNo={expected_seqno} - timeout exceeded ({time_missing*1000:.1f}ms)")
                            
                            # Remove from timer tracking
                            del self.missing_packet_timers[expected_seqno]
                            
                            # Move to next expected
                            if expected_seqno == self.next_expected_reliable_seqno:
                                self.next_expected_reliable_seqno += 1
                else:
                    # Packet has arrived, remove from missing timers if present
                    if expected_seqno in self.missing_packet_timers:
                        del self.missing_packet_timers[expected_seqno]