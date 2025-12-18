#!/usr/bin/env bash
set -euo pipefail

# ======= Shared configuration (same as training script) =======
SERVER_IP="128.143.71.13"   # iperf3 server IP
IFACE="ens160"              # outgoing network interface
PORT=5201
DURATION=30                 # duration per flow (seconds)
MSS=1460                    # used to estimate packets per BDP

# Algorithms (same order as training)
ALGOS=("bbr" "cubic" "reno" "vegas")

# ======= Test RTT / bandwidth / repetitions =======
REPEAT=2                    # number of runs per condition
TEST_RTTS=(30 80 150)       # new RTTs for testing
TEST_BWS=(20 75 300)        # new bandwidths for testing

# Test log directories (separate from training logs)
TEST_ROOT="test"
TEST_SS_DIR="${TEST_ROOT}/ss"
TEST_IPERF_DIR="${TEST_ROOT}/iperf"
mkdir -p "${TEST_SS_DIR}" "${TEST_IPERF_DIR}"

# ======= Compute queue size ≈ 1 BDP (same as training script) =======
calc_queue_pkts() {
    local rtt_ms=$1
    local bw_mbit=$2
    local mss=$3

    # BDP packets ≈ BW_MBIT * 1000 * RTT_MS / (8 * MSS)
    local num=$(( bw_mbit * 1000 * rtt_ms ))
    local den=$(( 8 * mss ))

    # ceiling(num / den)
    local pkts=$(( (num + den - 1) / den ))

    # Enforce a minimum queue size
    if (( pkts < 10 )); then
        pkts=10
    fi

    echo "${pkts}"
}

# ======= Configure link (mirrors training script exactly) =======
config_link() {
    local rtt_ms=$1
    local bw_mbit=$2
    local q_pkts=$3

    echo "[tc] Configure: dev=${IFACE}, RTT=${rtt_ms}ms, BW=${bw_mbit}Mbit, limit=${q_pkts} pkts"

    sudo tc qdisc del dev "${IFACE}" root 2>/dev/null || true

    # 1. HTB: enforce bottleneck bandwidth
    sudo tc qdisc add dev "${IFACE}" root handle 1: htb default 1
    sudo tc class add dev "${IFACE}" parent 1: classid 1:1 \
        htb rate ${bw_mbit}mbit ceil ${bw_mbit}mbit

    # 2. netem: simulate RTT and buffer (limit ≈ 1 BDP)
    sudo tc qdisc add dev "${IFACE}" parent 1:1 handle 10: netem \
        delay ${rtt_ms}ms limit ${q_pkts}

    # 3. fq_codel as the queue
    sudo tc qdisc add dev "${IFACE}" parent 10: handle 20: fq_codel

    echo "[tc] Current qdisc (before traffic):"
    sudo tc -s qdisc show dev "${IFACE}"
}

# ======= Run a single test flow (same logic as training) =======
run_one_flow() {
    local algo="$1"
    local rtt_ms="$2"
    local bw_mbit="$3"
    local run="$4"

    local flow_id="${algo}_rtt${rtt_ms}_bw${bw_mbit}_run${run}"
    echo "==== Running TEST flow: ${flow_id} ===="

    local ss_log="${TEST_SS_DIR}/${flow_id}.log"
    local iperf_log="${TEST_IPERF_DIR}/${flow_id}.json"

    # Start ss collector in the background
    python3 collect_ss.py \
        --port "${PORT}" \
        --dst "${SERVER_IP}" \
        --interval 0.5 \
        --algo "${algo}" \
        --output "${ss_log}" &
    local ss_pid=$!

    # Run iperf3 (single flow)
    iperf3 -c "${SERVER_IP}" -p "${PORT}" \
           -t "${DURATION}" -C "${algo}" \
           -i 0.5 -J > "${iperf_log}" || true

    # Stop ss collector
    kill "${ss_pid}" 2>/dev/null || true
    wait "${ss_pid}" 2>/dev/null || true

    echo "==== Done TEST flow: ${flow_id} ===="
    sleep 2
}

# ======= Main test loop: TEST_RTT × TEST_BW × algo × REPEAT =======
for rtt in "${TEST_RTTS[@]}"; do
    for bw in "${TEST_BWS[@]}"; do

        # Compute queue limit for this RTT/BW (≈ 1 BDP)
        QUEUE_PKTS=$(calc_queue_pkts "${rtt}" "${bw}" "${MSS}")
        echo
        echo "==============================="
        echo "  [TEST] RTT=${rtt} ms, BW=${bw} Mbit"
        echo "  queue ≈ ${QUEUE_PKTS} pkts (≈ 1 BDP)"
        echo "  logs under: ${TEST_ROOT}/ss and ${TEST_ROOT}/iperf"
        echo "==============================="

        # Configure link
        config_link "${rtt}" "${bw}" "${QUEUE_PKTS}"

        # Run each algorithm REPEAT times
        for algo in "${ALGOS[@]}"; do
            for run in $(seq 1 "${REPEAT}"); do
                run_one_flow "${algo}" "${rtt}" "${bw}" "${run}"
            done
        done

        echo "[tc] qdisc stats after TEST flows for RTT=${rtt}, BW=${bw}:"
        sudo tc -s qdisc show dev "${IFACE}"
    done
done

echo "All TEST experiments finished. Logs in ${TEST_ROOT}/ss and ${TEST_ROOT}/iperf"

