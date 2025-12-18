#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="128.143.71.13"   # iperf3 server IP
IFACE="ens160"              # 對外網卡
PORT=5201
DURATION=30                 # 每條 flow 跑 30 秒

# 這兩個會在迴圈中被覆寫
RTT_MS=10
BW_MBIT=10

# MSS 用來估算 1 BDP 對應多少 packets
MSS=1460

ALGOS=("bbr" "cubic" "reno" "vegas")

# RTT / 帶寬組合
RTTS=(10 50 100 200)
BWS=(10 50 100 500)

# 每個 (algo, rtt, bw) 組合跑幾次
RUNS=5

# 頂層 log 目錄
LOG_ROOT="logs"
LOG_SS_DIR="${LOG_ROOT}/ss"
LOG_IPERF_DIR="${LOG_ROOT}/iperf"
mkdir -p "${LOG_SS_DIR}" "${LOG_IPERF_DIR}"

# 根據 RTT / BW 計算 queue limit ≈ 1 BDP 的封包數（無上限）
calc_queue_pkts() {
    local rtt_ms=$1
    local bw_mbit=$2
    local mss=$3

    # BDP pkts ≈ BW_MBIT * 1000 * RTT_MS / (8 * MSS)
    local num=$(( bw_mbit * 1000 * rtt_ms ))
    local den=$(( 8 * mss ))

    # ceiling(num / den)
    local pkts=$(( (num + den - 1) / den ))

    # 保底最小值，避免太小
    if (( pkts < 10 )); then
        pkts=10
    fi

    echo "${pkts}"
}

config_link() {
    local rtt_ms=$1
    local bw_mbit=$2
    local q_pkts=$3

    echo "[tc] Configure: dev=${IFACE}, RTT=${rtt_ms}ms, BW=${bw_mbit}Mbit, limit=${q_pkts} pkts"

    sudo tc qdisc del dev "${IFACE}" root 2>/dev/null || true

    # 1. HTB control badnwidth
    sudo tc qdisc add dev "${IFACE}" root handle 1: htb default 1
    sudo tc class add dev "${IFACE}" parent 1: classid 1:1 \
        htb rate ${bw_mbit}mbit ceil ${bw_mbit}mbit

    # 2. netem simulate RTT + buffer
    sudo tc qdisc add dev "${IFACE}" parent 1:1 handle 10: netem \
        delay ${rtt_ms}ms limit ${q_pkts}

    # 3. fq_codel be queue
    sudo tc qdisc add dev "${IFACE}" parent 10: handle 20: fq_codel

    echo "[tc] Current qdisc (before traffic):"
    sudo tc -s qdisc show dev "${IFACE}"
}

run_one_flow() {
    local algo="$1"
    local run="$2"
    local flow_id="${algo}_rtt${RTT_MS}_bw${BW_MBIT}_run${run}"

    echo "==== Running flow: ${flow_id} ===="

    local ss_log="${LOG_SS_DIR}/${flow_id}.log"
    local iperf_log="${LOG_IPERF_DIR}/${flow_id}.json"

    # 背景啟動 ss collector
    python3 collect_ss.py \
        --port "${PORT}" \
        --dst "${SERVER_IP}" \
        --interval 0.5 \
        --algo "${algo}" \
        --output "${ss_log}" &
    local ss_pid=$!

    # 跑 iperf3（單條 flow）
    iperf3 -c "${SERVER_IP}" -p "${PORT}" \
           -t "${DURATION}" -C "${algo}" \
           -i 0.5 -J > "${iperf_log}" || true

    # 停掉 ss collector
    kill "${ss_pid}" 2>/dev/null || true
    wait "${ss_pid}" 2>/dev/null || true

    echo "==== Done: ${flow_id} ===="
    sleep 2
}

# 主實驗迴圈：每個 RTT × 每個 BW
for rtt in "${RTTS[@]}"; do
    for bw in "${BWS[@]}"; do
        RTT_MS=${rtt}
        BW_MBIT=${bw}

        # 動態算出這組 RTT/BW 下的 queue limit（≈ 1 BDP，無上限）
        QUEUE_PKTS=$(calc_queue_pkts "${RTT_MS}" "${BW_MBIT}" "${MSS}")
        echo "[calc] RTT=${RTT_MS} ms, BW=${BW_MBIT} Mbit -> queue ≈ ${QUEUE_PKTS} pkts (≈ 1 BDP)"

        echo
        echo "==============================="
        echo "  RTT=${RTT_MS} ms, BW=${BW_MBIT} Mbit"
        echo "  logs under: ${LOG_ROOT}/ss and ${LOG_ROOT}/iperf"
        echo "==============================="

        # 設定 link
        config_link "${RTT_MS}" "${BW_MBIT}" "${QUEUE_PKTS}"

        # 每個 algo 跑 RUNS 次
        for algo in "${ALGOS[@]}"; do
            for run in $(seq 1 "${RUNS}"); do
                run_one_flow "${algo}" "${run}"
            done
        done

        echo "[tc] qdisc stats after all flows for RTT=${RTT_MS}, BW=${BW_MBIT}:"
        sudo tc -s qdisc show dev "${IFACE}"
    done
done

echo "All algos finished for all RTT/BW combinations."
