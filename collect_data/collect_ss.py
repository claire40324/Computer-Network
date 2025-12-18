#!/usr/bin/env python3
import argparse
import subprocess
import time
import datetime
import re
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--interval", type=float, default=0.5)
parser.add_argument("--output", type=str, required=True)
parser.add_argument("--dst", type=str, default=None)      # server IP
parser.add_argument("--algo", type=str, required=True)    
args = parser.parse_args()

expected_algo = args.algo.lower()

# ====== Regex definition：get from ss second line ======
# for example:
#   cubic wscale:7,7 rtt:12.3/1.2 mss:1448 cwnd:1234 ssthresh:...
#   bytes_acked:12345 bytes_sent:23456 segs_out:123 segs_in:120 ...
#   pacing_rate 10.2Mbps
RE_RTT   = re.compile(r"rtt:(\d+\.?\d*)/(\d+\.?\d*)")
RE_CWND  = re.compile(r"cwnd:(\d+)")
RE_MSS   = re.compile(r"mss:(\d+)")
RE_SSTH  = re.compile(r"ssthresh:(\d+)")
RE_PACING = re.compile(r"pacing_rate (\d+\.?\d*)([KMG]?bps)")
RE_ACKED = re.compile(r"bytes_acked:(\d+)")
RE_SENT  = re.compile(r"bytes_sent:(\d+)")
RE_RECV  = re.compile(r"bytes_received:(\d+)")
RE_SEGS_O = re.compile(r"segs_out:(\d+)")
RE_SEGS_I = re.compile(r"segs_in:(\d+)")
RE_UNACK = re.compile(r"unacked:(\d+)")
RE_RETRANS = re.compile(r"retrans:(\d+)(?:/(\d+))?")
RE_ALGO = re.compile(r"\b(cubic|reno|bbr2?|bbr|vegas|yeah|westwood)\b")

def parse_rate_to_mbps(val_str, unit_str):
    """
    turn '10.2' + 'Mbps' to float(Mbps)
    default bits/s
    """
    try:
        val = float(val_str)
    except ValueError:
        return 0.0

    unit_str = unit_str or ""
    if unit_str.startswith("K"):
        return val / 1000.0
    elif unit_str.startswith("M"):
        return val
    elif unit_str.startswith("G"):
        return val * 1000.0
    else:
        # default -> bits/s
        return val / 1e6

# ======  ss command ======
filter_expr = f"dport = {args.port}"
if args.dst:
    filter_expr = f"dst {args.dst} dport = {args.port}"

cmd = ["ss", "-tiH", filter_expr]  # H: hide header, t: tcp, i: internal info

with open(args.output, "w") as f:
    header = (
        "wall_time monotonic algo "
        "rtt_ms rtt_var_ms cwnd mss "
        "pacing_mbps ssthresh "
        "bytes_acked bytes_sent bytes_received "
        "segs_out segs_in unacked retrans_total\n"
    )
    f.write(header)
    f.flush()

    while True:
        wall = datetime.datetime.now().isoformat()
        mono = time.monotonic()

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False
            )
        except Exception as e:
            print("ss error:", e, file=sys.stderr)
            time.sleep(args.interval)
            continue

        lines = result.stdout.strip().splitlines()
        if not lines:
            time.sleep(args.interval)
            continue

        # ss -tiH format：
        # column 0: "ESTAB ..."
        # column 1: "cubic wscale:... rtt:... cwnd:..."
        for i in range(0, len(lines), 2):
            if i + 1 >= len(lines):
                break
            info_line = lines[i + 1]

            # get algo，filter the flow is not this experiment
            m_algo = RE_ALGO.search(info_line)
            algo = m_algo.group(1).lower() if m_algo else "unknown"

            # bbr2 computer bbr
            if algo.startswith("bbr"):
                algo_norm = "bbr"
            else:
                algo_norm = algo

            if algo_norm != expected_algo:
                continue

            m_rtt = RE_RTT.search(info_line)
            m_cwnd = RE_CWND.search(info_line)

            if not (m_rtt and m_cwnd):
                continue

            rtt_ms = float(m_rtt.group(1))
            rtt_var = float(m_rtt.group(2))
            cwnd = int(m_cwnd.group(1))

            m_mss = RE_MSS.search(info_line)
            m_ssth = RE_SSTH.search(info_line)
            m_pace = RE_PACING.search(info_line)
            m_acked = RE_ACKED.search(info_line)
            m_sent = RE_SENT.search(info_line)
            m_recv = RE_RECV.search(info_line)
            m_out = RE_SEGS_O.search(info_line)
            m_in = RE_SEGS_I.search(info_line)
            m_unack = RE_UNACK.search(info_line)
            m_retr = RE_RETRANS.search(info_line)

            mss = int(m_mss.group(1)) if m_mss else 0
            ssthresh = int(m_ssth.group(1)) if m_ssth else -1

            if m_pace:
                pacing_mbps = parse_rate_to_mbps(m_pace.group(1), m_pace.group(2))
            else:
                pacing_mbps = 0.0

            bytes_acked = int(m_acked.group(1)) if m_acked else 0
            bytes_sent = int(m_sent.group(1)) if m_sent else 0
            bytes_received = int(m_recv.group(1)) if m_recv else 0
            segs_out = int(m_out.group(1)) if m_out else 0
            segs_in = int(m_in.group(1)) if m_in else 0
            unacked = int(m_unack.group(1)) if m_unack else 0

            if m_retr:
                retrans_total = int(m_retr.group(1))
            else:
                retrans_total = 0

            line = (
                f"{wall} {mono:.9f} {algo_norm} "
                f"{rtt_ms:.3f} {rtt_var:.3f} {cwnd} {mss} "
                f"{pacing_mbps:.6f} {ssthresh} "
                f"{bytes_acked} {bytes_sent} {bytes_received} "
                f"{segs_out} {segs_in} {unacked} {retrans_total}\n"
            )

            f.write(line)
            f.flush()

        time.sleep(args.interval)
