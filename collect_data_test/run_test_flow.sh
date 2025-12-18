#!/usr/bin/env bash
set -euo pipefail

# ======= 共用設定（跟訓練腳本一樣） =======
SERVER_IP="128.143.71.13"   # iperf3 server IP
IFACE="ens160"              # 對外網卡
PORT=5201
DURATION=30                 # 每條 flow 跑 30 秒
MSS=1460                    # 用來估算 1 BDP 對應多少 packets

# 演算法（跟訓練時一樣，順序也一樣）
ALGOS=("bbr" "cubic" "reno" "vegas")

# ======= 測試用的 RTT / BW / 次數 =======
REPEAT=2                    # 每組條件重複幾次（類似 RUNS）
TEST_RTTS=(30 80 150)       # 測試用新的 RTT
TEST_BWS=(20 75 300)        # 測試用新的 Bandwidth

# 測試 log 目錄（跟訓練 logs/ 分開）
TEST_ROOT="test"
TEST_SS_DIR="${TEST_ROOT}/ss"
TEST_IPERF_DIR="${TEST_ROOT}/iperf"
mkdir -p "${TEST_SS_DIR}" "${TEST_IPERF_DIR}"

# ======= 函式：算 queue 大小 ≈ 1 BDP（跟訓練腳本一樣） =======
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

# ======= 函式：設定 link（完全比照訓練腳本） =======
config_link() {
    local rtt_ms=$1
    local bw_mbit=$2
    local q_pkts=$3

    echo "[tc] Configure: dev=${IFACE}, RTT=${rtt_ms}ms, BW=${bw_mbit}Mbit, limit=${q_pkts} pkts"

    sudo tc qdisc del dev "${IFACE}" root 2>/dev/null || true

    # 1. HTB 控制瓶頸頻寬
    sudo tc qdisc add dev "${IFACE}" root handle 1: htb default 1
    sudo tc class add dev "${IFACE}" parent 1: classid 1:1 \
        htb rate ${bw_mbit}mbit ceil ${bw_mbit}mbit

    # 2. netem 模擬 RTT + buffer (limit ≈ 1 BDP)
    sudo tc qdisc add dev "${IFACE}" parent 1:1 handle 10: netem \
        delay ${rtt_ms}ms limit ${q_pkts}

    # 3. fq_codel 當 queue
    sudo tc qdisc add dev "${IFACE}" parent 10: handle 20: fq_codel

    echo "[tc] Current qdisc (before traffic):"
    sudo tc -s qdisc show dev "${IFACE}"
}

# ======= 函式：跑一條 flow（比照訓練腳本） =======
run_one_flow() {
    local algo="$1"
    local rtt_ms="$2"
    local bw_mbit="$3"
    local run="$4"

    local flow_id="${algo}_rtt${rtt_ms}_bw${bw_mbit}_run${run}"
    echo "==== Running TEST flow: ${flow_id} ===="

    local ss_log="${TEST_SS_DIR}/${flow_id}.log"
    local iperf_log="${TEST_IPERF_DIR}/${flow_id}.json"

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

    echo "==== Done TEST flow: ${flow_id} ===="
    sleep 2
}

# ======= 主測試迴圈：每個 TEST_RTT × TEST_BW × algo × REPEAT =======
for rtt in "${TEST_RTTS[@]}"; do
    for bw in "${TEST_BWS[@]}"; do

        # 算這組 RTT/BW 的 queue limit（≈ 1 BDP）
        QUEUE_PKTS=$(calc_queue_pkts "${rtt}" "${bw}" "${MSS}")
        echo
        echo "==============================="
        echo "  [TEST] RTT=${rtt} ms, BW=${bw} Mbit"
        echo "  queue ≈ ${QUEUE_PKTS} pkts (≈ 1 BDP)"
        echo "  logs under: ${TEST_ROOT}/ss and ${TEST_ROOT}/iperf"
        echo "==============================="

        # 設定 link
        config_link "${rtt}" "${bw}" "${QUEUE_PKTS}"

        # 每個 algo 跑 REPEAT 次
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

