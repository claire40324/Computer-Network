#!/usr/bin/env python3
import argparse
import json
import os
import re
import csv

parser = argparse.ArgumentParser()
parser.add_argument("--ss_dir", required=True, help="directory containing ss logs")
parser.add_argument("--json_dir", required=True, help="directory containing iperf3 json files")
parser.add_argument("--out_prefix", required=True, help="output prefix, e.g. data/features")
args = parser.parse_args()

# Filename format: algo_rtt{num}_bw{num}_run{num}
# Example: bbr_rtt200_bw500_run5.log / .json
NAME_RE = re.compile(r"(reno|bbr|cubic|vegas)_rtt(\d+)_bw(\d+)_run(\d+)", re.IGNORECASE)

def parse_name(fname):
    """Extract algo, rtt_setting, bw_setting, and run index from filename"""
    m = NAME_RE.search(fname)
    if not m:
        return None
    algo, rtt, bw, run = m.groups()
    return algo.lower(), int(rtt), int(bw), int(run)

def parse_json(json_path):
    """
    Extract the following fields from iperf3 JSON output:
      - ip_tp_mbps     : bits_per_second converted to Mbps
      - ip_mean_rtt_ms : mean_rtt (microseconds) converted to milliseconds
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        sender_end = data["end"]["streams"][0]["sender"]

        bits_per_second = float(sender_end["bits_per_second"])
        tp_mbps = bits_per_second / 1e6

        mean_rtt_us = float(sender_end.get("mean_rtt", 0.0))  # microseconds
        mean_rtt_ms = mean_rtt_us / 1000.0

        return {
            "ip_tp_mbps": tp_mbps,
            "ip_mean_rtt_ms": mean_rtt_ms,
        }
    except Exception as e:
        print(f"[warn] parse_json failed for {json_path}: {e}")
        return None

def parse_ss_last_line(ss_path):
    """
    Extract the last record from an ss log.
    Expected format:
      wall_time monotonic algo rtt_ms rtt_var_ms cwnd mss pacing_mbps ...

    Convert it into:
      ss_rtt_ms, ss_rtt_var_ms, ss_cwnd_bytes, ss_pacing_mbps
    """
    try:
        with open(ss_path, "r") as f:
            lines = f.read().strip().splitlines()

        if len(lines) <= 1:
            # Header only or empty file
            return None

        last = lines[-1].split()
        if len(last) < 8:
            return None

        ss_rtt_ms = float(last[3])
        ss_rtt_var_ms = float(last[4])
        cwnd_segs = int(last[5])
        mss_bytes = int(last[6])
        pacing_mbps = float(last[7])

        # Normalize cwnd to bytes
        cwnd_bytes = cwnd_segs * mss_bytes

        return {
            "ss_rtt_ms": ss_rtt_ms,
            "ss_rtt_var_ms": ss_rtt_var_ms,
            "ss_cwnd_bytes": cwnd_bytes,
            "ss_pacing_mbps": pacing_mbps,
        }
    except Exception as e:
        print(f"[warn] parse_ss_last_line failed for {ss_path}: {e}")
        return None

rows = []

for fname in os.listdir(args.ss_dir):
    if not fname.endswith(".log"):
        continue

    parsed = parse_name(fname)
    if not parsed:
        print(f"[skip] filename not matched: {fname}")
        continue

    algo, rtt_setting, bw_setting, run = parsed

    ss_path = os.path.join(args.ss_dir, fname)
    json_path = os.path.join(args.json_dir, fname.replace(".log", ".json"))

    if not os.path.exists(json_path):
        print(f"[warn] missing JSON file for {fname}")
        continue

    ss_feat = parse_ss_last_line(ss_path)
    json_feat = parse_json(json_path)

    if not ss_feat or not json_feat:
        print(f"[warn] missing features for {fname}")
        continue

    row = {
        "algo": algo,
        "rtt_setting": rtt_setting,   # ms
        "bw_setting": bw_setting,     # Mbps
        "run": run,
    }
    row.update(ss_feat)
    row.update(json_feat)
    rows.append(row)

if not rows:
    print("No data merged!")
    raise SystemExit(0)

# ---------- Write output WITH RTT/BW conditions ----------
out_with = args.out_prefix + "_with_cond.csv"
fieldnames_with = [
    "algo",
    "rtt_setting", "bw_setting", "run",
    "ss_rtt_ms", "ss_rtt_var_ms",
    "ss_cwnd_bytes",
    "ss_pacing_mbps",
    "ip_tp_mbps",
    "ip_mean_rtt_ms",
]

with open(out_with, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames_with)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r[k] for k in fieldnames_with})

print(f"[OK] saved: {out_with}")

# ---------- Write output WITHOUT RTT/BW conditions ----------
out_no = args.out_prefix + "_no_cond.csv"
fieldnames_no = [
    "algo",
    "run",
    "ss_rtt_ms", "ss_rtt_var_ms",
    "ss_cwnd_bytes",
    "ss_pacing_mbps",
    "ip_tp_mbps",
    "ip_mean_rtt_ms",
]

with open(out_no, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames_no)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r[k] for k in fieldnames_no})

print(f"[OK] saved: {out_no}")
