#!/usr/bin/env python3
import os
import sys
import csv
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==========================================
# Configuration & Paths
# ==========================================
WORKSPACE_ROOT = "/home/yixuanfu/2026Summer/AI_and_X/Lab"
GEM5_DIR = os.path.join(WORKSPACE_ROOT, "gem5")
GEM5_BIN = os.path.join(GEM5_DIR, "build/NULL/gem5.opt")
CONFIG_SCRIPT = os.path.join(GEM5_DIR, "configs/example/garnet_synth_traffic.py")
DATA_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/data/lab2_task1")
FIGURES_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/reports/figures")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

TRAFFIC_PATTERNS = ["uniform_random", "neighbor", "transpose", "tornado", "shuffle"]

INJECTION_RATES = [
    0.01, 0.03, 0.05, 0.08, 0.10,
    0.12, 0.14, 0.16, 0.18, 0.20,
    0.22, 0.24, 0.26, 0.28, 0.30,
    0.35, 0.40, 0.45, 0.50
]

# Total simulation cycles = 10,000 cycles
# At 1GHz (1000 ps/cycle), sim_cycles in Ticks = 10,000 * 1000 = 10,000,000
CLOCK_PERIOD_TICKS = 1000
ACTUAL_CYCLES = 10000
SIM_CYCLES_TICKS = ACTUAL_CYCLES * CLOCK_PERIOD_TICKS
NUM_CPUS = 64
NUM_DIRS = 64
MESH_ROWS = 8


def run_single_simulation(args):
    traffic, rate = args
    out_dir = os.path.join(DATA_DIR, traffic, f"inj_{rate:.3f}")
    os.makedirs(out_dir, exist_ok=True)
    
    cmd = [
        GEM5_BIN,
        "-d", out_dir,
        CONFIG_SCRIPT,
        "--network=garnet",
        f"--num-cpus={NUM_CPUS}",
        f"--num-dirs={NUM_DIRS}",
        "--topology=Mesh_XY",
        f"--mesh-rows={MESH_ROWS}",
        "--inj-vnet=0",
        f"--synthetic={traffic}",
        f"--sim-cycles={SIM_CYCLES_TICKS}",
        f"--injectionrate={rate:.3f}"
    ]
    
    log_file = os.path.join(out_dir, "run.log")
    with open(log_file, "w") as f:
        res = subprocess.run(cmd, cwd=GEM5_DIR, stdout=f, stderr=subprocess.STDOUT)
        
    stats_file = os.path.join(out_dir, "stats.txt")
    data = parse_stats(stats_file, traffic, rate)

    # Clean up large/redundant files generated automatically by gem5
    for item in ["config.ini", "config.json", "run.log"]:
        p = os.path.join(out_dir, item)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    fs_dir = os.path.join(out_dir, "fs")
    if os.path.exists(fs_dir):
        import shutil
        shutil.rmtree(fs_dir, ignore_errors=True)

    return data


def parse_stats(stats_file, traffic, rate):
    metrics = {
        "traffic_pattern": traffic,
        "injection_rate": rate,
        "packets_injected": 0,
        "packets_received": 0,
        "avg_queueing_latency_ticks": 0.0,
        "avg_network_latency_ticks": 0.0,
        "avg_packet_latency_ticks": 0.0,
        "avg_packet_latency_cycles": 0.0,
        "avg_hops": 0.0,
        "reception_rate": 0.0,
        "avg_link_utilization": 0.0
    }
    
    if not os.path.exists(stats_file):
        print(f"Warning: {stats_file} not found for {traffic} at rate {rate}")
        return metrics
        
    with open(stats_file, "r") as f:
        for line in f:
            if "system.ruby.network.packets_injected::total" in line:
                parts = line.split()
                if len(parts) >= 2:
                    metrics["packets_injected"] = int(parts[1])
            elif "system.ruby.network.packets_received::total" in line:
                parts = line.split()
                if len(parts) >= 2:
                    metrics["packets_received"] = int(parts[1])
            elif "system.ruby.network.average_packet_queueing_latency" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "nan":
                    metrics["avg_queueing_latency_ticks"] = float(parts[1])
            elif "system.ruby.network.average_packet_network_latency" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "nan":
                    metrics["avg_network_latency_ticks"] = float(parts[1])
            elif "system.ruby.network.average_packet_latency" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "nan":
                    metrics["avg_packet_latency_ticks"] = float(parts[1])
            elif "system.ruby.network.average_hops" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "nan":
                    metrics["avg_hops"] = float(parts[1])
            elif "system.ruby.network.avg_link_utilization" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "nan":
                    metrics["avg_link_utilization"] = float(parts[1])
                    
    # Latency in cycles
    metrics["avg_packet_latency_cycles"] = metrics["avg_packet_latency_ticks"] / CLOCK_PERIOD_TICKS
    # Reception rate: total_packets_received / (num_cpus * sim_cycles)
    metrics["reception_rate"] = metrics["packets_received"] / (NUM_CPUS * ACTUAL_CYCLES)
    
    return metrics


def save_summary_csv(results):
    csv_file = os.path.join(DATA_DIR, "summary_lab2_task1.csv")
    fieldnames = [
        "traffic_pattern",
        "injection_rate",
        "packets_injected",
        "packets_received",
        "avg_queueing_latency_ticks",
        "avg_network_latency_ticks",
        "avg_packet_latency_ticks",
        "avg_packet_latency_cycles",
        "avg_hops",
        "reception_rate",
        "avg_link_utilization"
    ]
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda x: (x["traffic_pattern"], x["injection_rate"])):
            writer.writerow(row)
    print(f"[✓] Summary CSV saved to: {csv_file}")


def plot_curves(results):
    # Organize data by traffic pattern
    data = {}
    for traffic in TRAFFIC_PATTERNS:
        data[traffic] = []
        
    for r in results:
        data[r["traffic_pattern"]].append(r)
        
    for traffic in TRAFFIC_PATTERNS:
        data[traffic].sort(key=lambda x: x["injection_rate"])

    colors = {
        "uniform_random": "#1f77b4",
        "neighbor": "#2ca02c",
        "transpose": "#ff7f0e",
        "tornado": "#d62728",
        "shuffle": "#9467bd"
    }
    markers = {
        "uniform_random": "o",
        "neighbor": "s",
        "transpose": "^",
        "tornado": "D",
        "shuffle": "v"
    }

    # 1. Latency vs Reception Rate (Throughput)
    plt.figure(figsize=(9, 6), dpi=300)
    for traffic in TRAFFIC_PATTERNS:
        pts = data[traffic]
        x = [p["reception_rate"] for p in pts]
        y = [p["avg_packet_latency_cycles"] for p in pts]
        plt.plot(x, y, marker=markers[traffic], label=traffic, color=colors[traffic], linewidth=2, markersize=6)
        
    plt.title("Latency vs Throughput (8x8 Mesh, 10,000 Cycles)", fontsize=14, fontweight="bold", pad=12)
    plt.xlabel("Throughput / Reception Rate (packets/node/cycle)", fontsize=12)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, frameon=True)
    plt.tight_layout()
    plot_file = os.path.join(FIGURES_DIR, "lab2_task1_latency_throughput.png")
    plt.savefig(plot_file)
    plt.savefig(os.path.join(FIGURES_DIR, "lab2_task1_latency_throughput.pdf"))
    plt.close()
    print(f"[✓] Plot saved to: {plot_file}")

    # 2. Latency vs Injection Rate
    plt.figure(figsize=(9, 6), dpi=300)
    for traffic in TRAFFIC_PATTERNS:
        pts = data[traffic]
        x = [p["injection_rate"] for p in pts]
        y = [p["avg_packet_latency_cycles"] for p in pts]
        plt.plot(x, y, marker=markers[traffic], label=traffic, color=colors[traffic], linewidth=2, markersize=6)
        
    plt.title("Latency vs Injection Rate (8x8 Mesh, 10,000 Cycles)", fontsize=14, fontweight="bold", pad=12)
    plt.xlabel("Injection Rate (packets/node/cycle)", fontsize=12)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, frameon=True)
    plt.tight_layout()
    plot_file2 = os.path.join(FIGURES_DIR, "lab2_task1_latency_vs_injrate.png")
    plt.savefig(plot_file2)
    plt.savefig(os.path.join(FIGURES_DIR, "lab2_task1_latency_vs_injrate.pdf"))
    plt.close()
    print(f"[✓] Plot saved to: {plot_file2}")

    # 3. Throughput vs Injection Rate
    plt.figure(figsize=(9, 6), dpi=300)
    for traffic in TRAFFIC_PATTERNS:
        pts = data[traffic]
        x = [p["injection_rate"] for p in pts]
        y = [p["reception_rate"] for p in pts]
        plt.plot(x, y, marker=markers[traffic], label=traffic, color=colors[traffic], linewidth=2, markersize=6)
        
    # Add ideal x=y dashed line
    plt.plot([0, 0.5], [0, 0.5], "k--", alpha=0.5, label="Ideal (No Drop/Saturation)")
    plt.title("Throughput vs Injection Rate (8x8 Mesh, 10,000 Cycles)", fontsize=14, fontweight="bold", pad=12)
    plt.xlabel("Injection Rate (packets/node/cycle)", fontsize=12)
    plt.ylabel("Reception Rate / Throughput (packets/node/cycle)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, frameon=True)
    plt.tight_layout()
    plot_file3 = os.path.join(FIGURES_DIR, "lab2_task1_throughput_vs_injrate.png")
    plt.savefig(plot_file3)
    plt.savefig(os.path.join(FIGURES_DIR, "lab2_task1_throughput_vs_injrate.pdf"))
    plt.close()
    print(f"[✓] Plot saved to: {plot_file3}")


def main():
    tasks = []
    for traffic in TRAFFIC_PATTERNS:
        for rate in INJECTION_RATES:
            tasks.append((traffic, rate))
            
    print(f"[*] Starting {len(tasks)} simulation runs with parallel workers...")
    max_workers = min(16, os.cpu_count() or 8)
    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_simulation, task): task for task in tasks}
        completed_count = 0
        for future in as_completed(futures):
            task = futures[future]
            try:
                res = future.result()
                results.append(res)
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == len(tasks):
                    print(f"    Progress: {completed_count}/{len(tasks)} runs completed ({completed_count * 100 // len(tasks)}%)")
            except Exception as e:
                print(f"[!] Task {task} generated an exception: {e}")
                
    print("[*] All simulations finished. Processing data...")
    save_summary_csv(results)
    plot_curves(results)
    print("[✓] Lab2 Task 1 completed successfully!")


if __name__ == "__main__":
    main()
