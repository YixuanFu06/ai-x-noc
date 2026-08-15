#!/bin/bash
# Usage: ./extract_network_stats.sh [stats_file] [output_file] [num_cpus] [sim_cycles]

STATS_FILE=${1:-m5out/stats.txt}
OUTPUT_FILE=${2:-network_stats.txt}
NUM_CPUS=${3:-64}
SIM_CYCLES=${4:-10000}

if [ ! -f "$STATS_FILE" ]; then
    echo "Error: $STATS_FILE not found."
    exit 1
fi

PACKETS_RECEIVED=$(grep "system.ruby.network.packets_received::total" "$STATS_FILE" | awk '{print $2}')
if [ -z "$PACKETS_RECEIVED" ]; then
    PACKETS_RECEIVED=0
fi

# Reception Rate (packets/node/cycle) = total_packets_received / (num_cpus * sim_cycles)
RECEPTION_RATE=$(awk -v pr="$PACKETS_RECEIVED" -v cpus="$NUM_CPUS" -v cycles="$SIM_CYCLES" 'BEGIN { printf "%.8f", pr / (cpus * cycles) }')

echo > "$OUTPUT_FILE"
grep "system.ruby.network.packets_injected::total" "$STATS_FILE" | sed 's/system.ruby.network.packets_injected::total\s*/packets_injected = /' >> "$OUTPUT_FILE"
grep "system.ruby.network.packets_received::total" "$STATS_FILE" | sed 's/system.ruby.network.packets_received::total\s*/packets_received = /' >> "$OUTPUT_FILE"
grep "system.ruby.network.average_packet_queueing_latency" "$STATS_FILE" | sed 's/system.ruby.network.average_packet_queueing_latency\s*/average_packet_queueing_latency = /' >> "$OUTPUT_FILE"
grep "system.ruby.network.average_packet_network_latency" "$STATS_FILE" | sed 's/system.ruby.network.average_packet_network_latency\s*/average_packet_network_latency = /' >> "$OUTPUT_FILE"
grep "system.ruby.network.average_packet_latency" "$STATS_FILE" | sed 's/system.ruby.network.average_packet_latency\s*/average_packet_latency = /' >> "$OUTPUT_FILE"
grep "system.ruby.network.average_hops" "$STATS_FILE" | sed 's/system.ruby.network.average_hops\s*/average_hops = /' >> "$OUTPUT_FILE"
echo "reception_rate = $RECEPTION_RATE (packets/node/cycle)" >> "$OUTPUT_FILE"

cat "$OUTPUT_FILE"
