import time
from typing import List, Dict, Optional


class NetworkMetrics:
    def __init__(self):
        # Timing
        self.start_time = time.time()

        # Sender-side counters
        self.total_sent = 0
        self.total_sent_reliable = 0
        self.total_sent_unreliable = 0
        self.bytes_sent_reliable = 0
        self.bytes_sent_unreliable = 0

        # Receiver-side counters
        self.total_received = 0
        self.total_recv_reliable = 0
        self.total_recv_unreliable = 0
        self.bytes_recv_reliable = 0
        self.bytes_recv_unreliable = 0

        # Latency tracking (receiver measures one-way, sender measures RTT)
        self.rtt_records: List[float] = []  # Sender-side RTT
        self.one_way_latency_reliable: List[float] = []  # Receiver-side
        self.one_way_latency_unreliable: List[float] = []  # Receiver-side

        # Jitter calculation (RFC3550) - receiver-side
        self.jitter_reliable = 0.0
        self.jitter_unreliable = 0.0
        self.last_transit_reliable = None
        self.last_transit_unreliable = None

        # Sequence number tracking (receiver-side for loss calculation)
        self.max_seen_reliable_seqno = 0
        self.max_seen_unreliable_seqno = 0
        self.received_reliable_seqnos = set()
        self.received_unreliable_seqnos = set()

    def record_packet_sent(self, payload_size: int, is_reliable: bool = True):
        """Record a packet being sent (sender-side)"""
        self.total_sent += 1
        if is_reliable:
            self.total_sent_reliable += 1
            self.bytes_sent_reliable += payload_size
        else:
            self.total_sent_unreliable += 1
            self.bytes_sent_unreliable += payload_size

    def record_packet_received(
        self,
        payload_size: int,
        seqno: int,
        sender_timestamp: float,
        is_reliable: bool = True,
    ):
        """Record a packet being received with latency calculation (receiver-side)"""
        self.total_received += 1

        if is_reliable:
            self.total_recv_reliable += 1
            self.bytes_recv_reliable += payload_size
            self.received_reliable_seqnos.add(seqno)
            self._update_latency_and_jitter(sender_timestamp, True, seqno)
        else:
            self.total_recv_unreliable += 1
            self.bytes_recv_unreliable += payload_size
            self.received_unreliable_seqnos.add(seqno)
            self._update_latency_and_jitter(sender_timestamp, False, seqno)

    def record_rtt(self, rtt: float):
        """Record round-trip time for reliable packets (sender-side)"""
        self.rtt_records.append(rtt)

    def _update_latency_and_jitter(
        self, sender_timestamp: float, is_reliable: bool, seqno: int
    ):
        """Internal method to calculate one-way latency and jitter"""
        current_time = time.time()
        transit = current_time - sender_timestamp

        if is_reliable:
            if seqno > self.max_seen_reliable_seqno:
                self.max_seen_reliable_seqno = seqno

            self.one_way_latency_reliable.append(transit)

            # Jitter calculation (RFC3550)
            if self.last_transit_reliable is not None:
                d = transit - self.last_transit_reliable
                self.jitter_reliable += (abs(d) - self.jitter_reliable) / 16.0
            self.last_transit_reliable = transit
        else:
            if seqno > self.max_seen_unreliable_seqno:
                self.max_seen_unreliable_seqno = seqno

            self.one_way_latency_unreliable.append(transit)

            # Jitter calculation (RFC3550)
            if self.last_transit_unreliable is not None:
                d = transit - self.last_transit_unreliable
                self.jitter_unreliable += (abs(d) - self.jitter_unreliable) / 16.0
            self.last_transit_unreliable = transit

    def get_metrics_report(self, label: str = "") -> Dict:
        """Generate metrics report as a dictionary (supports both sender and receiver perspectives)"""
        duration = time.time() - self.start_time
        
        is_sender = "Sender" in label
        is_receiver = "Receiver" in label

        # Calculate averages for latency
        avg_rtt_ms = (
            (sum(self.rtt_records) / len(self.rtt_records) * 1000.0)
            if self.rtt_records
            else 0.0
        )
        avg_ow_reliable_ms = (
            (
                sum(self.one_way_latency_reliable)
                / len(self.one_way_latency_reliable)
                * 1000.0
            )
            if self.one_way_latency_reliable
            else 0.0
        )
        avg_ow_unreliable_ms = (
            (
                sum(self.one_way_latency_unreliable)
                / len(self.one_way_latency_unreliable)
                * 1000.0
            )
            if self.one_way_latency_unreliable
            else 0.0
        )

        jitter_reliable_ms = self.jitter_reliable * 1000.0
        jitter_unreliable_ms = self.jitter_unreliable * 1000.0

        # Throughput calculations
        send_thr_reliable_bps = (
            (self.bytes_sent_reliable / duration) if duration > 0 else 0.0
        )
        send_thr_unreliable_bps = (
            (self.bytes_sent_unreliable / duration) if duration > 0 else 0.0
        )
        send_thr_total_bps = (
            ((self.bytes_sent_reliable + self.bytes_sent_unreliable) / duration)
            if duration > 0
            else 0.0
        )
        
        recv_thr_reliable_bps = (
            (self.bytes_recv_reliable / duration) if duration > 0 else 0.0
        )
        recv_thr_unreliable_bps = (
            (self.bytes_recv_unreliable / duration) if duration > 0 else 0.0
        )
        recv_thr_total_bps = (
            ((self.bytes_recv_reliable + self.bytes_recv_unreliable) / duration)
            if duration > 0
            else 0.0
        )

        # Calculate expected packets from sequence number tracking (receiver-side)
        expected_reliable = self.max_seen_reliable_seqno
        expected_unreliable = self.max_seen_unreliable_seqno
        lost_reliable = expected_reliable - len(self.received_reliable_seqnos)
        lost_unreliable = expected_unreliable - len(self.received_unreliable_seqnos)

        # Packet Delivery Ratio calculation
        # Sender-side: PDR = (Packets Received / Packets Sent) * 100%
        # Receiver-side: PDR = (Packets Received / Packets Expected from sequence) * 100%
        if is_receiver:
            # Use max sequence number seen as "expected" (what was actually sent)
            pdr_reliable = (
                (self.total_recv_reliable / expected_reliable * 100.0)
                if expected_reliable > 0
                else 0.0
            )
            pdr_unreliable = (
                (self.total_recv_unreliable / expected_unreliable * 100.0)
                if expected_unreliable > 0
                else 0.0
            )
        elif is_sender:
            # Sender perspective: use what we sent
            pdr_reliable = (
                (self.total_recv_reliable / self.total_sent_reliable * 100.0)
                if self.total_sent_reliable > 0
                else 0.0
            )
            pdr_unreliable = (
                (self.total_recv_unreliable / self.total_sent_unreliable * 100.0)
                if self.total_sent_unreliable > 0
                else 0.0
            )
        else:
            # Fallback: use received/sent ratio
            pdr_reliable = (
                (self.total_recv_reliable / self.total_sent_reliable * 100.0)
                if self.total_sent_reliable > 0
                else 0.0
            )
            pdr_unreliable = (
                (self.total_recv_unreliable / self.total_sent_unreliable * 100.0)
                if self.total_sent_unreliable > 0
                else 0.0
            )

        return {
            "label": label,
            "duration": duration,
            "overall": {
                "packets_sent": self.total_sent,
                "packets_received": self.total_received,
                "send_throughput_bps": send_thr_total_bps,
                "recv_throughput_bps": recv_thr_total_bps,
            },
            "reliable": {
                "packets_sent": self.total_sent_reliable,
                "packets_received": self.total_recv_reliable,
                "packets_lost": lost_reliable,
                "send_throughput_bps": send_thr_reliable_bps,
                "recv_throughput_bps": recv_thr_reliable_bps,
                "avg_rtt_ms": avg_rtt_ms,
                "avg_latency_ms": avg_ow_reliable_ms,
                "jitter_ms": jitter_reliable_ms,
                "delivery_ratio_pct": pdr_reliable,
            },
            "unreliable": {
                "packets_sent": self.total_sent_unreliable,
                "packets_received": self.total_recv_unreliable,
                "packets_lost": lost_unreliable,
                "send_throughput_bps": send_thr_unreliable_bps,
                "recv_throughput_bps": recv_thr_unreliable_bps,
                "avg_latency_ms": avg_ow_unreliable_ms,
                "jitter_ms": jitter_unreliable_ms,
                "delivery_ratio_pct": pdr_unreliable,
            },
        }
    
    def print_metrics(self, label, loaded_metrics=None):
        """Print formatted metrics report (supports both sender and receiver perspectives)"""
        metrics = loaded_metrics if loaded_metrics else self.get_metrics_report(label)
        
        is_sender = "Sender" in label
        is_receiver = "Receiver" in label
        
        print(f"\n=== PERFORMANCE METRICS [{label}] ===")
        print(f"Duration:                     {metrics['duration']:.2f}s")
        
        if is_sender:
            print(f"Total Packets Sent:           {metrics['overall']['packets_sent']}")
            print(f"Send Throughput:              {metrics['overall']['send_throughput_bps']:.2f} bytes/sec")
        
        if is_receiver:
            print(f"Total Packets Received:       {metrics['overall']['packets_received']}")
            print(f"Receive Throughput:           {metrics['overall']['recv_throughput_bps']:.2f} bytes/sec")

        print("\n-- Reliable Channel --")
        if is_sender:
            print(f"Packets Sent:                 {metrics['reliable']['packets_sent']}")
            print(f"Send Throughput:              {metrics['reliable']['send_throughput_bps']:.2f} bytes/sec")
            print(f"Average RTT:                  {metrics['reliable']['avg_rtt_ms']:.2f} ms")
        
        if is_receiver:
            print(f"Packets Received:             {metrics['reliable']['packets_received']}")
            print(f"Packets Lost:                 {metrics['reliable']['packets_lost']}")
            print(f"Receive Throughput:           {metrics['reliable']['recv_throughput_bps']:.2f} bytes/sec")
            print(f"Avg One-way Latency:          {metrics['reliable']['avg_latency_ms']:.2f} ms")
            print(f"Jitter (RFC3550):             {metrics['reliable']['jitter_ms']:.2f} ms")
            print(f"Packet Delivery Ratio:        {metrics['reliable']['delivery_ratio_pct']:.2f}%")
        elif is_sender and metrics['reliable']['delivery_ratio_pct'] == 0.0:
            # Sender doesn't have receiver data
            print(f"Packet Delivery Ratio:        N/A (requires receiver data)")
        else:
            print(f"Packet Delivery Ratio:        {metrics['reliable']['delivery_ratio_pct']:.2f}%")

        print("\n-- Unreliable Channel --")
        if is_sender:
            print(f"Packets Sent:                 {metrics['unreliable']['packets_sent']}")
            print(f"Send Throughput:              {metrics['unreliable']['send_throughput_bps']:.2f} bytes/sec")
        
        if is_receiver:
            print(f"Packets Received:             {metrics['unreliable']['packets_received']}")
            print(f"Packets Lost:                 {metrics['unreliable']['packets_lost']}")
            print(f"Receive Throughput:           {metrics['unreliable']['recv_throughput_bps']:.2f} bytes/sec")
            print(f"Avg One-way Latency:          {metrics['unreliable']['avg_latency_ms']:.2f} ms")
            print(f"Jitter (RFC3550):             {metrics['unreliable']['jitter_ms']:.2f} ms")
            print(f"Packet Delivery Ratio:        {metrics['unreliable']['delivery_ratio_pct']:.2f}%")
        elif is_sender and metrics['unreliable']['delivery_ratio_pct'] == 0.0:
            # Sender doesn't have receiver data
            print(f"Packet Delivery Ratio:        N/A (requires receiver data)")
        else:
            print(f"Packet Delivery Ratio:        {metrics['unreliable']['delivery_ratio_pct']:.2f}%")
        print("=" * 60 + "\n")
