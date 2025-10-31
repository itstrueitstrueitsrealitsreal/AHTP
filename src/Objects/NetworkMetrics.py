import time
from typing import List, Dict, Optional

class NetworkMetrics:
    def __init__(self):
        # Timing
        self.start_time = time.time()
        
        # Overall counters
        self.total_sent = 0
        self.total_received = 0
        
        # Channel-specific counters
        self.total_sent_reliable = 0
        self.total_sent_unreliable = 0
        self.total_recv_reliable = 0
        self.total_recv_unreliable = 0
        
        # Throughput tracking
        self.bytes_sent_reliable = 0
        self.bytes_sent_unreliable = 0
        self.bytes_recv_reliable = 0
        self.bytes_recv_unreliable = 0
        
        # Latency tracking
        self.latency_records: List[float] = []
        self.one_way_latency_reliable: List[float] = []
        self.one_way_latency_unreliable: List[float] = []
        
        # Jitter calculation (RFC3550)
        self.jitter_reliable = 0.0
        self.jitter_unreliable = 0.0
        self.last_transit_reliable = None
        self.last_transit_unreliable = None
        
        # Sequence number tracking
        self.max_seen_reliable_seqno = 0
        self.max_seen_unreliable_seqno = 0
    
    def record_packet_sent(self, payload_size: int, is_reliable: bool = True):
        """Record a packet being sent with payload size"""
        self.total_sent += 1
        if is_reliable:
            self.total_sent_reliable += 1
            self.bytes_sent_reliable += payload_size
        else:
            self.total_sent_unreliable += 1
            self.bytes_sent_unreliable += payload_size
    
    def record_packet_received(self, payload_size: int, seqno: int, 
                             sender_timestamp: float, is_reliable: bool = True):
        """Record a packet being received with latency calculation"""
        self.total_received += 1
        
        if is_reliable:
            self.total_recv_reliable += 1
            self.bytes_recv_reliable += payload_size
            self._update_latency_and_jitter(sender_timestamp, True, seqno)
        else:
            self.total_recv_unreliable += 1
            self.bytes_recv_unreliable += payload_size
            self._update_latency_and_jitter(sender_timestamp, False, seqno)
    
    def record_rtt(self, rtt: float):
        """Record round-trip time for reliable packets"""
        self.latency_records.append(rtt)
    
    def _update_latency_and_jitter(self, sender_timestamp: float, 
                                 is_reliable: bool, seqno: int):
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
        """Generate metrics report as a dictionary"""
        duration = time.time() - self.start_time
        
        # Calculate averages and rates
        avg_rtt_ms = (sum(self.latency_records) / len(self.latency_records) * 1000.0) if self.latency_records else 0.0
        avg_ow_reliable_ms = (sum(self.one_way_latency_reliable) / len(self.one_way_latency_reliable) * 1000.0) if self.one_way_latency_reliable else 0.0
        avg_ow_unreliable_ms = (sum(self.one_way_latency_unreliable) / len(self.one_way_latency_unreliable) * 1000.0) if self.one_way_latency_unreliable else 0.0
        
        jitter_reliable_ms = self.jitter_reliable * 1000.0
        jitter_unreliable_ms = self.jitter_unreliable * 1000.0
        
        # Send throughput calculations
        send_thr_reliable_bps = (self.bytes_sent_reliable / duration) if duration > 0 else 0.0
        send_thr_unreliable_bps = (self.bytes_sent_unreliable / duration) if duration > 0 else 0.0
        send_thr_total_bps = ((self.bytes_sent_reliable + self.bytes_sent_unreliable) / duration) if duration > 0 else 0.0
        
        # Receive throughput calculations
        recv_thr_reliable_bps = (self.bytes_recv_reliable / duration) if duration > 0 else 0.0
        recv_thr_unreliable_bps = (self.bytes_recv_unreliable / duration) if duration > 0 else 0.0
        recv_thr_total_bps = ((self.bytes_recv_reliable + self.bytes_recv_unreliable) / duration) if duration > 0 else 0.0
        
        denom_reliable = self.total_sent_reliable if self.total_sent_reliable > 0 else self.max_seen_reliable_seqno
        denom_unreliable = self.total_sent_unreliable if self.total_sent_unreliable > 0 else self.max_seen_unreliable_seqno
        
        pdr_reliable = (self.total_recv_reliable / denom_reliable * 100.0) if denom_reliable > 0 else 0.0
        pdr_unreliable = (self.total_recv_unreliable / denom_unreliable * 100.0) if denom_unreliable > 0 else 0.0
        
        return {
            'label': label,
            'duration': duration,
            'overall': {
                'packets_sent': self.total_sent,
                'packets_received': self.total_received,
                'send_throughput_bps': send_thr_total_bps,
                'recv_throughput_bps': recv_thr_total_bps,
                'avg_rtt_ms': avg_rtt_ms
            },
            'reliable': {
                'packets_sent': self.total_sent_reliable,
                'packets_received': self.total_recv_reliable,
                'send_throughput_bps': send_thr_reliable_bps,
                'recv_throughput_bps': recv_thr_reliable_bps,
                'avg_latency_ms': avg_ow_reliable_ms,
                'jitter_ms': jitter_reliable_ms,
                'delivery_ratio_pct': pdr_reliable
            },
            'unreliable': {
                'packets_sent': self.total_sent_unreliable,
                'packets_received': self.total_recv_unreliable,
                'send_throughput_bps': send_thr_unreliable_bps,
                'recv_throughput_bps': recv_thr_unreliable_bps,
                'avg_latency_ms': avg_ow_unreliable_ms,
                'jitter_ms': jitter_unreliable_ms,
                'delivery_ratio_pct': pdr_unreliable
            }
        }
    
    def print_metrics(self, label):
        """Print formatted metrics report (maintains current interface)"""
        metrics = self.get_metrics_report(label)
        
        print(f"\n=== PERFORMANCE METRICS [{label}] ===")

        if label == "Receiver-side":
            print(f"Duration:                     {metrics['duration']:.2f}s")
            print(f"Total Packets Received:       {metrics['overall']['packets_received']}")
            print(f"Receive Throughput:           {metrics['overall']['recv_throughput_bps']:.2f} bytes/sec")
            
            print("\n-- Reliable Channel --")
            print(f"Packets Received:             {metrics['reliable']['packets_received']}")
            print(f"Receive Throughput:           {metrics['reliable']['recv_throughput_bps']:.2f} bytes/sec")
            print(f"Avg One-way Latency:          {metrics['reliable']['avg_latency_ms']:.2f} ms")
            print(f"Jitter (RFC3550):             {metrics['reliable']['jitter_ms']:.2f} ms")
            print(f"Packet Delivery Ratio:        {metrics['reliable']['delivery_ratio_pct']:.2f}%")
            
            print("\n-- Unreliable Channel --")
            print(f"Packets Received:             {metrics['unreliable']['packets_received']}")
            print(f"Receive Throughput:           {metrics['unreliable']['recv_throughput_bps']:.2f} bytes/sec")
            print(f"Avg One-way Latency:          {metrics['unreliable']['avg_latency_ms']:.2f} ms")
            print(f"Jitter (RFC3550):             {metrics['unreliable']['jitter_ms']:.2f} ms")
            print(f"Packet Delivery Ratio:        {metrics['unreliable']['delivery_ratio_pct']:.2f}%")
            print("="*60 + "\n")

        if label == "Sender-side":
            print(f"Duration:                     {metrics['duration']:.2f}s")
            print(f"Total Packets Sent:           {metrics['overall']['packets_sent']}")
            print(f"Send Throughput:              {metrics['overall']['send_throughput_bps']:.2f} bytes/sec")
            print(f"Average RTT (Reliable only):  {metrics['overall']['avg_rtt_ms']:.2f} ms")
            
            print("\n-- Reliable Channel --")
            print(f"Packets Sent:                 {metrics['reliable']['packets_sent']}")
            print(f"Send Throughput:              {metrics['reliable']['send_throughput_bps']:.2f} bytes/sec")
            
            print("\n-- Unreliable Channel --")
            print(f"Packets Sent:                 {metrics['unreliable']['packets_sent']}")
            print(f"Send Throughput:              {metrics['unreliable']['send_throughput_bps']:.2f} bytes/sec")
            print("="*60 + "\n")
