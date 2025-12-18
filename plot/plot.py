#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

LOG_SS_DIR = "logs_10_10/ss"
RTT_MS = 10
BW_MBIT = 10
RUN = 1

algos = ["bbr", "cubic", "reno", "vegas"]
colors = {
    "bbr": "C0",
    "cubic": "C1",
    "reno": "C2",
    "vegas": "C3",
}

# ss log 欄位（依照你現在的輸出）
SS_COLS = [
    "wall_time", "monotonic", "algo",
    "rtt_ms", "rtt_var_ms",
    "cwnd", "mss", "pacing_mbps",
    "ssthresh",
    "bytes_acked", "bytes_sent", "bytes_received",
    "segs_out", "segs_in", "unacked", "retrans_total",
]

plt.rcParams["figure.dpi"] = 150
plt.rcParams["font.size"] = 10


def load_ss_log(path):
    """讀取一個 ss log，回傳 DataFrame"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r") as f:
        first_line = f.readline()

    # 如果第一行是 header，就 skiprows=1
    if first_line.startswith("wall_time"):
        df = pd.read_csv(path, delim_whitespace=True, skiprows=1, names=SS_COLS)
    else:
        df = pd.read_csv(path, delim_whitespace=True, names=SS_COLS)

    return df


def plot_line_metric(metric, ylabel, title_prefix, filename_prefix):
    """畫其中一種 metric"""
    plt.figure(figsize=(10, 3))
    for algo in algos:
        fname = f"{algo}_rtt{RTT_MS}_bw{BW_MBIT}_run{RUN}.log"
        path = os.path.join(LOG_SS_DIR, fname)
        if not os.path.exists(path):
            print(f"[WARN] file not found: {path}")
            continue

        df = load_ss_log(path)
        t = df["monotonic"] - df["monotonic"].iloc[0]

        if metric == "cwnd":
            y = df["cwnd"] * df["mss"]  # seg → bytes
        else:
            y = df[metric]

        plt.plot(t, y, label=algo, color=colors.get(algo, None), alpha=0.85)

    plt.xlabel("Time (s)")
    plt.ylabel(ylabel)
    plt.title(f"{title_prefix} (rtt={RTT_MS} ms, bw={BW_MBIT} Mbps, run={RUN})")
    plt.legend(title="algo")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    out = f"{filename_prefix}_rtt{RTT_MS}_bw{BW_MBIT}_run{RUN}.png"
    plt.savefig(out)
    print(f"[OK] Saved: {out}")
    plt.close()


def main():
    # 1️⃣ cwnd(bytes)
    plot_line_metric(
        metric="cwnd",
        ylabel="cwnd (bytes)",
        title_prefix="cwnd",
        filename_prefix="cwnd"
    )

    # 2️⃣ pacing rate (Mbps)
    plot_line_metric(
        metric="pacing_mbps",
        ylabel="pacing (Mbps)",
        title_prefix="pacing",
        filename_prefix="pacing"
    )

    # 3️⃣ RTT variation (ms)
    plot_line_metric(
        metric="rtt_var_ms",
        ylabel="RTT var (ms)",
        title_prefix="RTT variation",
        filename_prefix="rttvar"
    )


if __name__ == "__main__":
    main()
