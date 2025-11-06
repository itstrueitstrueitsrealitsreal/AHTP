import json, glob, matplotlib.pyplot as plt
import pandas as pd

files = sorted(glob.glob("results/*.json"))
rows = []

for f in files:
    data = json.load(open(f))
    label = f.split("/")[-1].replace(".json", "")
    rows.append({
        "test": label,
        "loss": label.split("_")[1].replace("loss","") if "loss" in label else "0",
        "reliable_latency": data["reliable"]["avg_latency_ms"],
        "unreliable_latency": data["unreliable"]["avg_latency_ms"],
        "reliable_jitter": data["reliable"]["jitter_ms"],
        "unreliable_jitter": data["unreliable"]["jitter_ms"],
        "reliable_thr": data["reliable"]["recv_throughput_bps"],
        "unreliable_thr": data["unreliable"]["recv_throughput_bps"],
        "pdr_reliable": data["reliable"]["delivery_ratio_pct"],
        "pdr_unreliable": data["unreliable"]["delivery_ratio_pct"],
    })

df = pd.DataFrame(rows)

# --- Latency ---
plt.figure()
plt.plot(df["loss"], df["reliable_latency"], "o-", label="Reliable")
plt.plot(df["loss"], df["unreliable_latency"], "s-", label="Unreliable")
plt.xlabel("Packet Loss (%)")
plt.ylabel("Average One-way Latency (ms)")
plt.title("Latency vs. Packet Loss")
plt.legend()
plt.grid(True)
plt.savefig("fig_latency.png", dpi=300)

# --- Jitter ---
plt.figure()
plt.plot(df["loss"], df["reliable_jitter"], "o-", label="Reliable")
plt.plot(df["loss"], df["unreliable_jitter"], "s-", label="Unreliable")
plt.xlabel("Packet Loss (%)")
plt.ylabel("Jitter (ms)")
plt.title("Jitter vs. Packet Loss")
plt.legend()
plt.grid(True)
plt.savefig("fig_jitter.png", dpi=300)

# --- Throughput ---
plt.figure()
plt.plot(df["loss"], df["reliable_thr"], "o-", label="Reliable")
plt.plot(df["loss"], df["unreliable_thr"], "s-", label="Unreliable")
plt.xlabel("Packet Loss (%)")
plt.ylabel("Throughput (bytes/sec)")
plt.title("Throughput vs. Packet Loss")
plt.legend()
plt.grid(True)
plt.savefig("fig_throughput.png", dpi=300)
