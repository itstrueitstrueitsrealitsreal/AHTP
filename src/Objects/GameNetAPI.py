import asyncio
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import StreamDataReceived, DatagramFrameReceived
import time
import struct
from .NetworkMetrics import NetworkMetrics


class GameNetProtocol(QuicConnectionProtocol):
    """Extended QUIC protocol that handles events"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = None

    def quic_event_received(self, event):
        """Handle QUIC events - THIS IS THE CORRECT METHOD"""
        print(f"[DEBUG] Event received: {event.__class__.__name__}")
        if isinstance(event, StreamDataReceived):
            print(
                f"[DEBUG] StreamDataReceived event with data length {len(event.data)}"
            )
            # Reliable channel data (stream)
            if self.api:
                self.api.process_received_data(event.data, is_reliable=True)
        elif isinstance(event, DatagramFrameReceived):
            print(
                f"[DEBUG] DatagramFrameReceived event with data length {len(event.data)}"
            )
            # Unreliable channel data (datagram)
            if self.api:
                self.api.process_received_data(event.data, is_reliable=False)


class GameNetAPI:
    def __init__(self, connection):
        self.connection = connection

        # Separate sequence numbers
        self.reliable_seqno = 0
        self.unreliable_seqno = 0

        # Sender-side: Track packets waiting for ACK
        self.pending_acks = {}

        # Receiver-side: Buffer and reordering
        self.reliable_buffer = {}
        self.packet_arrival_times = {}
        self.next_expected_reliable_seqno = 1

        self.retransmit_timeout = 0.5  # 500ms default (give-up threshold)
        self.retransmit_interval = 0.1  # retransmit every 100ms until give-up
        self.receiver_callback = None

        # Skipping lost packets after timeout
        self.missing_packet_timers = {}

        # Sliding window for reliable channel
        self.window_size = 5
        self.base = 1
        self.next_seqno = 1
        self.acked_packets = set()

        # Metrics
        self.metrics = NetworkMetrics()

        # Simulated network loss probabilities for testing scenarios
        self.loss_probability_reliable = 0.0
        self.loss_probability_unreliable = 0.0

    async def send_packet(self, data, is_reliable=True):
        """Send a packet through appropriate channel"""
        # Store full timestamp for metrics, truncated for packet header
        full_timestamp = time.time()
        timestamp = int(full_timestamp * 1000) & 0xFFFFFFFF

        if is_reliable:
            # Wait until window has space (BEFORE assigning seqno)
            wait_count = 0
            while self.next_seqno >= self.base + self.window_size:
                if wait_count % 10 == 0:  # Only print every 10th wait to reduce spam
                    print(
                        f"[Window full] waiting for ACKs... (base={self.base}, next={self.next_seqno})"
                    )
                wait_count += 1
                await asyncio.sleep(
                    0.05
                )  # Longer sleep to allow retransmissions to happen

            # Now assign sequence number
            seqno = self.next_seqno
            self.next_seqno += 1
            channel_type = 0

        else:
            self.unreliable_seqno += 1
            seqno = self.unreliable_seqno
            channel_type = 1

        # Construct packet header
        header = struct.pack("!BHI", channel_type, seqno, timestamp)
        payload = data.encode("utf-8") if isinstance(data, str) else data
        packet_data = header + payload

        # Record packet sent in metrics
        payload_size = len(payload)
        self.metrics.record_packet_sent(payload_size, is_reliable)

        if is_reliable:
            # Track for RTT and possible retransmission
            # Track both first_sent (for give-up) and last_sent (for retransmit interval)
            self.pending_acks[seqno] = {
                "first_sent": full_timestamp,
                "last_sent": full_timestamp,
                "packet_data": packet_data,
                "retransmit_count": 0,
                "payload_size": payload_size,
            }

            # Use QUIC stream for reliable delivery
            stream_id = 0
            self.connection._quic.send_stream_data(
                stream_id, packet_data, end_stream=False
            )
            print(f"[SEND] Reliable SeqNo={seqno}, Data='{data[:40]}...'")
        else:
            # Use QUIC datagram for unreliable delivery
            self.connection._quic.send_datagram_frame(packet_data)
            print(f"[SEND] Unreliable SeqNo={seqno}, Data='{data[:40]}...'")
        # Transmit
        self.connection.transmit()

    def process_ack(self, seqno):
        """Process cumulative ACK - everything up to seqno has been received"""
        # Cumulative ACK means receiver has everything from 1 to seqno in order
        print(
            f"[DEBUG] Processing cumulative ACK for SeqNo={seqno}, current base={self.base}"
        )

        # Mark all packets up to seqno as acked
        for seq in range(self.base, min(seqno + 1, self.next_seqno)):
            if seq in self.pending_acks:
                # Calculate RTT from first sent time
                rtt = time.time() - self.pending_acks[seq]["first_sent"]
                self.metrics.record_rtt(rtt)
                del self.pending_acks[seq]
            self.acked_packets.add(seq)

        # Slide window base to seqno + 1
        old_base = self.base
        self.base = max(self.base, seqno + 1)

        if self.base != old_base:
            print(
                f"[ACK] Cumulative ACK for SeqNo={seqno}, New base={self.base} (advanced from {old_base})"
            )
        else:
            print(
                f"[ACK] Cumulative ACK for SeqNo={seqno}, Base unchanged at {self.base}"
            )

        return None  # Can't calculate accurate individual RTT with cumulative ACKs

    async def check_retransmissions(self):
        """Check for packets that need retransmission or give-up"""
        current_time = time.time()

        for seqno in range(self.base, self.next_seqno):
            if seqno in self.pending_acks and seqno not in self.acked_packets:
                packet_info = self.pending_acks[seqno]
                # Total time since first send
                elapsed_total = current_time - packet_info["first_sent"]
                # Time since last retransmission
                elapsed_since_last = current_time - packet_info["last_sent"]

                # Give up if total elapsed exceeds retransmit_timeout (200ms)
                if elapsed_total > self.retransmit_timeout:
                    print(
                        f"[GIVEUP] SeqNo={seqno} - no ACK after {elapsed_total*1000:.1f} ms (giving up)"
                    )
                    # Record loss in metrics
                    self.metrics.record_packet_lost(
                        packet_info.get("payload_size", 0), is_reliable=True
                    )

                    # Remove from pending and mark as acked/lost so window can advance
                    del self.pending_acks[seqno]
                    self.acked_packets.add(seqno)

                    # Advance base while possible
                    while self.base in self.acked_packets:
                        self.base += 1

                    continue

                # Retransmit if enough time has passed since last send
                if elapsed_since_last >= self.retransmit_interval:
                    print(
                        f"[Retransmit] SeqNo={seqno} (since_last={elapsed_since_last*1000:.1f} ms, attempt={packet_info['retransmit_count']+1})"
                    )
                    self.connection._quic.send_stream_data(
                        0, packet_info["packet_data"], end_stream=False
                    )
                    self.connection.transmit()
                    packet_info["last_sent"] = current_time
                    packet_info["retransmit_count"] += 1

    async def start_retransmit_loop(self):
        """Background task to check retransmissions"""
        while True:
            await asyncio.sleep(0.1)
            await self.check_retransmissions()

    def set_receive_callback(self, callback):
        """Set callback for received packets"""
        self.receiver_callback = callback

    def _reconstruct_timestamp(self, truncated_timestamp_ms):
        """Reconstruct full timestamp from 32-bit truncated value"""
        current_time_ms = int(time.time() * 1000)

        # Handle 32-bit overflow by finding the closest full timestamp
        # that matches the truncated value
        base = current_time_ms & ~0xFFFFFFFF  # Clear lower 32 bits
        candidate1 = base | truncated_timestamp_ms
        candidate2 = (base - (1 << 32)) | truncated_timestamp_ms
        candidate3 = (base + (1 << 32)) | truncated_timestamp_ms

        # Choose the candidate closest to current time
        candidates = [candidate1, candidate2, candidate3]
        best_candidate = min(candidates, key=lambda x: abs(x - current_time_ms))

        return best_candidate / 1000.0  # Convert to seconds

    def process_received_data(self, data, is_reliable=True):
        """Process raw received data"""
        if len(data) < 7:
            return

        channel_type, seqno, timestamp = struct.unpack("!BHI", data[:7])
        payload = data[7:].decode("utf-8", errors="ignore")
        arrival_time = time.time()

        # Check if this is an ACK packet (using bit flag)
        is_ack = bool(channel_type & 0b10)
        actual_channel = channel_type & 0b01

        if is_ack:
            print(f"[DEBUG] Received ACK for SeqNo={seqno}")
            self.process_ack(seqno)
            return

        if actual_channel == 0:  # Reliable channel
            print(f"[RECV] Reliable SeqNo={seqno}, Data='{payload[:40]}...'")

            # Track arrival time
            self.packet_arrival_times[seqno] = arrival_time

            # Buffer and reorder
            self.reliable_buffer[seqno] = (seqno, actual_channel, payload, timestamp)

            # Check for missing packets and skip if timeout exceeded
            self._check_and_skip_missing_packets()

            # Deliver in-order packets
            while self.next_expected_reliable_seqno in self.reliable_buffer:
                pkt = self.reliable_buffer.pop(self.next_expected_reliable_seqno)
                seq_delivered = pkt[0]
                payload_str = pkt[2]
                send_ts_ms = pkt[3]
                arrival_ts = self.packet_arrival_times.get(seq_delivered, time.time())

                # Record packet reception
                payload_size = len(payload_str.encode("utf-8"))
                sender_timestamp = self._reconstruct_timestamp(send_ts_ms)
                self.metrics.record_packet_received(
                    payload_size, seq_delivered, sender_timestamp, is_reliable=True
                )

                if self.receiver_callback:
                    self.receiver_callback(*pkt)

                self.next_expected_reliable_seqno += 1

            # SEND ACK for EVERY packet received (not just in-order ones)
            # Send cumulative ACK for the highest in-order packet
            ack_seqno = self.next_expected_reliable_seqno - 1  # Last delivered seqno

            # But also send individual ACK for out-of-order packets to trigger fast retransmit
            if seqno > ack_seqno:
                # This is an out-of-order packet, send duplicate cumulative ACK
                print(
                    f"[Out-of-order] Received SeqNo={seqno}, but expecting {self.next_expected_reliable_seqno}"
                )

            if ack_seqno > 0:
                ack_flag = 0b10  # ACK bit set
                ack_header = struct.pack(
                    "!BHI",
                    ack_flag,
                    ack_seqno,  # Send cumulative ACK (highest in-order seqno)
                    int(time.time() * 1000) & 0xFFFFFFFF,
                )
                self.connection._quic.send_stream_data(0, ack_header, end_stream=False)
                self.connection.transmit()
                print(
                    f"[ACK SENT] Cumulative ACK for SeqNo={ack_seqno} (expecting {self.next_expected_reliable_seqno})"
                )

        else:  # Unreliable channel
            print(f"[RECV] Unreliable SeqNo={seqno}, Data='{payload[:40]}...'")

            # Record packet reception with metrics component
            payload_size = len(payload.encode("utf-8"))
            sender_timestamp = self._reconstruct_timestamp(timestamp)
            self.metrics.record_packet_received(
                payload_size, seqno, sender_timestamp, is_reliable=False
            )

            if self.receiver_callback:
                print(f"[Inside RECV callback] Unreliable SeqNo={seqno}")
                self.receiver_callback(seqno, actual_channel, payload, timestamp)
            print(f"[After RECV callback] Unreliable SeqNo={seqno}")

    def _check_and_skip_missing_packets(self):
        """Check for missing packets and skip if timeout exceeded"""
        current_time = time.time()
        arrived_seqnos = set(self.reliable_buffer.keys())

        if arrived_seqnos:
            max_arrived = max(arrived_seqnos)

            for expected_seqno in range(
                self.next_expected_reliable_seqno, max_arrived + 1
            ):
                if expected_seqno not in arrived_seqnos:
                    if expected_seqno not in self.missing_packet_timers:
                        self.missing_packet_timers[expected_seqno] = current_time
                    else:
                        time_missing = (
                            current_time - self.missing_packet_timers[expected_seqno]
                        )

                        if time_missing > self.retransmit_timeout:
                            print(
                                f"[Skip] SeqNo={expected_seqno} - timeout exceeded ({time_missing*1000:.1f}ms)"
                            )
                            del self.missing_packet_timers[expected_seqno]

                            if expected_seqno == self.next_expected_reliable_seqno:
                                self.next_expected_reliable_seqno += 1
                else:
                    if expected_seqno in self.missing_packet_timers:
                        del self.missing_packet_timers[expected_seqno]

    def compute_metrics(self, label: str = ""):
        """Print performance metrics using NetworkMetrics component"""
        self.metrics.print_metrics(label)
