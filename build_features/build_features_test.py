#!/usr/bin/env python3
import argparse
import json
import os
import re
import csv

parser = argparse.ArgumentParser()
parser.add_argument("--ss_dir", required=True)
parser.add_argument("--json_dir", required=True)
parser.add_argument("--out_no_cond", required=True)
args = parser.parse_args()

NAME_RE = re.compile(r"(reno|bbr|cubic|vegas)_rtt(\d+)_bw(\d+)_run(\d+)", re.IGNORECASE)

def parse_name(fname):
    m = NAME_RE.search(fname)
    if not m:
        return None
    algo, rtt, bw, run = m.groups()
    return algo.lower(), int(rtt), int(bw), int(run)

def parse_json(json_path):
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        end = data["end"]["streams"][0]["sender"]
        return {
            "ip_tp_mbps": end["bits_per_second"] / 1e6,
            "ip_mean_rtt_ms": end.get("mean_rtt", 0) / 1000.0,
        }
    except Exception as e:
        print("[json parse error]", json_path, e)
        return None

def parse_ss_log(ss_path):
    try:
        with open(ss_path, "r") as f:
            lines = f.read().strip().splitlines()
        if len(lines) <= 1:
            return None
        last = lines[-1].split()
        return {
            "ss_rtt_ms": float(last[3]),
            "ss_rtt_var_ms": float(last[4]),
            "ss_cwnd_bytes": int(last[5]) * int(last[6]),
            "ss_pacing_mbps": float(last[7]),
        }
    except Exception as e:
        print("[ss parse error]", ss_path, e)
        return None

rows_no_cond = []

for fname in os.listdir(args.ss_dir):
    if not fname.endswith(".log"):
        continue

    parsed = parse_name(fname)
    if not parsed:
        continue

    algo, rtt, bw, run = parsed
    ss_path = os.path.join(args.ss_dir, fname)
    json_path = os.path.join(args.json_dir, fname.replace(".log", ".json"))

    if not os.path.exists(json_path):
        print(f"[warn] no JSON for {fname}")
        continue

    ss_feat = parse_ss_log(ss_path)
    json_feat = parse_json(json_path)

    if not ss_feat or not json_feat:
        continue

    row = {
        "algo": algo,
        "run": run,
    }
    row.update(ss_feat)
    row.update(json_feat)

    rows_no_cond.append(row)

if rows_no_cond:
    with open(args.out_no_cond, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_no_cond[0].keys()))
        writer.writeheader()
        for r in rows_no_cond:
            writer.writerow(r)
    print(f"[OK] saved no-cond features: {args.out_no_cond}")
else:
    print("No rows parsed!")
