# plot_metrics.py
"""
Plots latency, jitter, throughput, and packet delivery ratio
under different test conditions (reliable vs unreliable).

Input folders:
  results/metrics-*.json   -> sender metrics
  results/Receiver-*.json  -> receiver metrics

Outputs:
  figures/latency.png
  figures/jitter.png
  figures/throughput.png
  figures/pdr.png
  figures/combined_summary.csv
"""

import json
import glob
import os
import matplotlib.pyplot as plt
import pandas as pd

RESULTS_DIR = "results"
os.makedirs("figures", exist_ok=True)

# -------------------------------------------------------------------
# 1. Load Sender Metrics
# -------------------------------------------------------------------
sender_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "Sender-*.json")))
sender_rows = []

for f in sender_files:
    try:
        data = json.load(open(f))
        label = data.get("label", os.path.basename(f))
        overall = data["overall"]
        channel = "Unreliable" if "unreliable" in label.lower() else "Reliable"

        sender_rows.append({
            "label": label.replace("metrics-", ""),
            "channel": channel,
            "duration_s": data["duration"],
            "throughput_bps_send": overall["send_throughput_bps"],
            "rtt_ms": overall["avg_rtt_ms"]
        })
    except Exception as e:
        print(f"[WARN] Skipping sender file {f}: {e}")

df_sender = pd.DataFrame(sender_rows)

# -------------------------------------------------------------------
# 2. Load Receiver Metrics (for latency, jitter, PDR)
# -------------------------------------------------------------------
receiver_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "Receiver-*.json")))
receiver_rows = []

for f in receiver_files:
    try:
        data = json.load(open(f))
        r = data["reliable"]
        label = os.path.basename(f)
        receiver_rows.append({
            "label": label,
            "latency_ms": r["avg_latency_ms"],
            "jitter_ms": r["jitter_ms"],
            "throughput_bps_recv": r["recv_throughput_bps"],
            "pdr_pct": r["delivery_ratio_pct"]
        })
    except Exception as e:
        print(f"[WARN] Skipping receiver file {f}: {e}")

# Average multiple receiver runs
df_recv = pd.DataFrame(receiver_rows)
if not df_recv.empty:
    df_recv["label"] = "Receiver-Aggregated"
    df_recv = df_recv.mean(numeric_only=True).to_frame().T

# -------------------------------------------------------------------
# 3. Merge sender and receiver data
# -------------------------------------------------------------------
if not df_sender.empty and not df_recv.empty:
    # Combine averages into one summary table
    summary = {
        "Latency (ms)": df_recv["latency_ms"].iloc[0],
        "Jitter (ms)": df_recv["jitter_ms"].iloc[0],
        "Throughput (bytes/sec)": df_sender["throughput_bps_send"].mean(),
        "Packet Delivery Ratio (%)": df_recv["pdr_pct"].iloc[0]
    }
    print("\n=== Combined Summary (Average) ===")
    for k, v in summary.items():
        print(f"{k:30}: {v:.2f}")

# -------------------------------------------------------------------
# 4. Plot per-test sender metrics
# -------------------------------------------------------------------
metrics_to_plot = [
    ("rtt_ms", "Average RTT (ms)", "RTT per Test"),
    ("throughput_bps_send", "Send Throughput (bytes/sec)", "Throughput per Test"),
]

for metric, ylabel, title in metrics_to_plot:
    plt.figure(figsize=(8, 4))
    colors = df_sender["channel"].map({"Reliable": "steelblue", "Unreliable": "orange"})
    plt.bar(df_sender["label"], df_sender[metric], color=colors)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=20, ha="right")
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    out = f"figures/{metric}.png"
    plt.savefig(out, dpi=300)
    print(f"Saved {out}")

# -------------------------------------------------------------------
# 5. Plot receiver-based metrics (latency, jitter, PDR)
# -------------------------------------------------------------------
if not df_recv.empty:
    metrics_recv = [
        ("latency_ms", "Average One-Way Latency (ms)", "Latency"),
        ("jitter_ms", "Jitter (ms)", "Jitter"),
        ("throughput_bps_recv", "Receive Throughput (bytes/sec)", "Throughput"),
        ("pdr_pct", "Packet Delivery Ratio (%)", "Reliability (PDR)"),
    ]
    for metric, ylabel, title in metrics_recv:
        plt.figure(figsize=(6, 4))
        plt.bar(["Receiver"], [df_recv[metric].iloc[0]], color="green")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.tight_layout()
        out = f"figures/{metric}.png"
        plt.savefig(out, dpi=300)
        print(f"Saved {out}")

# -------------------------------------------------------------------
# 6. Export summary CSV
# -------------------------------------------------------------------
df_sender.to_csv("figures/sender_summary.csv", index=False)
if not df_recv.empty:
    df_recv.to_csv("figures/receiver_summary.csv", index=False)
print("Exported CSV summaries to ./figures/")
