#!/usr/bin/env python3
import os
import sys
import csv
import shutil
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
DATA_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/data/lab3_task1")
FIGURES_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/reports/figures")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# 10,000 clock cycles at 1GHz (1000 ps/cycle)
CLOCK_PERIOD_TICKS = 1000
ACTUAL_CYCLES = 10000
SIM_CYCLES_TICKS = ACTUAL_CYCLES * CLOCK_PERIOD_TICKS
NUM_CPUS = 16
NUM_DIRS = 16

INJECTION_RATES = [
    0.01, 0.03, 0.05, 0.08, 0.10,
    0.12, 0.15, 0.18, 0.20, 0.25,
    0.30, 0.35, 0.40, 0.45, 0.50
]

TRAFFIC_PATTERNS = ["uniform_random", "neighbor", "transpose", "tornado", "shuffle"]


def run_simulation(args):
    topo, routing_algo, mesh_rows, traffic, rate = args
    out_dir = os.path.join(DATA_DIR, topo, traffic, f"inj_{rate:.3f}")
    os.makedirs(out_dir, exist_ok=True)
    
    cmd = [
        GEM5_BIN,
        "-d", out_dir,
        CONFIG_SCRIPT,
        "--network=garnet",
        f"--num-cpus={NUM_CPUS}",
        f"--num-dirs={NUM_DIRS}",
        f"--topology={topo}",
        f"--routing-algorithm={routing_algo}",
        "--inj-vnet=0",
        f"--synthetic={traffic}",
        f"--sim-cycles={SIM_CYCLES_TICKS}",
        f"--injectionrate={rate:.3f}"
    ]
    if topo == "Mesh_XY":
        cmd.append(f"--mesh-rows={mesh_rows}")
        
    log_file = os.path.join(out_dir, "run.log")
    with open(log_file, "w") as f:
        res = subprocess.run(cmd, cwd=GEM5_DIR, stdout=f, stderr=subprocess.STDOUT)
        
    stats_file = os.path.join(out_dir, "stats.txt")
    data = parse_stats(stats_file, topo, traffic, rate)

    # Automatic cleanup of redundant files
    for item in ["config.ini", "config.json", "run.log"]:
        p = os.path.join(out_dir, item)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    fs_dir = os.path.join(out_dir, "fs")
    if os.path.exists(fs_dir):
        shutil.rmtree(fs_dir, ignore_errors=True)

    return data


def parse_stats(stats_file, topo, traffic, rate):
    metrics = {
        "topology": topo,
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
        print(f"Warning: {stats_file} not found for {topo}-{traffic} at rate {rate}")
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
                    
    metrics["avg_packet_latency_cycles"] = metrics["avg_packet_latency_ticks"] / CLOCK_PERIOD_TICKS
    metrics["reception_rate"] = metrics["packets_received"] / (NUM_CPUS * ACTUAL_CYCLES)
    
    return metrics


def save_summary_csv(results):
    csv_file = os.path.join(DATA_DIR, "summary_lab3_task1.csv")
    fieldnames = [
        "topology", "traffic_pattern", "injection_rate",
        "packets_injected", "packets_received",
        "avg_queueing_latency_ticks", "avg_network_latency_ticks",
        "avg_packet_latency_ticks", "avg_packet_latency_cycles",
        "avg_hops", "reception_rate", "avg_link_utilization"
    ]
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda x: (x["topology"], x["traffic_pattern"], x["injection_rate"])):
            writer.writerow(row)
    print(f"[✓] Summary CSV saved to: {csv_file}")


def plot_results(results):
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

    # 1. Ring Topology - All Traffic Patterns (Latency vs Throughput)
    ring_results = [r for r in results if r["topology"] == "Ring"]
    ring_grouped = {}
    for r in ring_results:
        ring_grouped.setdefault(r["traffic_pattern"], []).append(r)
        
    plt.figure(figsize=(9, 6), dpi=300)
    for traffic, pts in ring_grouped.items():
        pts.sort(key=lambda x: x["reception_rate"])
        x = [p["reception_rate"] for p in pts]
        y = [p["avg_packet_latency_cycles"] for p in pts]
        plt.plot(x, y, marker=markers.get(traffic, "o"), label=traffic,
                 color=colors.get(traffic, "black"), linewidth=2, markersize=6)
                 
    plt.title("Ring Topology (16 Nodes): Latency vs. Throughput", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Throughput / Reception Rate (packets/node/cycle)", fontsize=11)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=10, frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "lab3_task1_ring_latency_throughput.png"))
    plt.savefig(os.path.join(FIGURES_DIR, "lab3_task1_ring_latency_throughput.pdf"))
    plt.close()

    # 2. Ring vs. 4x4 Mesh Comparison (Uniform Random & Tornado)
    plt.figure(figsize=(9, 6), dpi=300)
    comp_patterns = ["uniform_random", "tornado", "neighbor"]
    comp_colors = {"Ring": "#d62728", "Mesh_XY": "#1f77b4"}
    comp_linestyles = {"uniform_random": "-", "tornado": "--", "neighbor": ":"}

    for topo in ["Ring", "Mesh_XY"]:
        for traffic in comp_patterns:
            pts = [r for r in results if r["topology"] == topo and r["traffic_pattern"] == traffic]
            if not pts:
                continue
            pts.sort(key=lambda x: x["reception_rate"])
            x = [p["reception_rate"] for p in pts]
            y = [p["avg_packet_latency_cycles"] for p in pts]
            label = f"{topo} ({traffic})"
            plt.plot(x, y, label=label, color=colors[traffic],
                     linestyle="-" if topo == "Ring" else "--",
                     marker="o" if topo == "Ring" else "s",
                     linewidth=2, markersize=5)

    plt.title("16-Node Comparison: Ring (1D-Torus) vs. 4x4 Mesh", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Throughput / Reception Rate (packets/node/cycle)", fontsize=11)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=9, frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "lab3_task1_ring_vs_mesh_comparison.png"))
    plt.savefig(os.path.join(FIGURES_DIR, "lab3_task1_ring_vs_mesh_comparison.pdf"))
    plt.close()

    print("[✓] High-res plots generated successfully!")


def main():
    tasks = []

    # 1. 16-Node Ring Topology with custom routing (routing-algorithm=2)
    for traffic in TRAFFIC_PATTERNS:
        for rate in INJECTION_RATES:
            tasks.append(("Ring", 2, 0, traffic, rate))

    # 2. 16-Node 4x4 Mesh Topology with XY routing (routing-algorithm=1) for comparison
    for traffic in ["uniform_random", "tornado", "neighbor"]:
        for rate in INJECTION_RATES:
            tasks.append(("Mesh_XY", 1, 4, traffic, rate))

    print(f"[*] Total simulation runs: {len(tasks)}")
    max_workers = min(16, os.cpu_count() or 8)
    
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_simulation, task): task for task in tasks}
        completed_count = 0
        for future in as_completed(futures):
            task = futures[future]
            try:
                res = future.result()
                results.append(res)
                completed_count += 1
                if completed_count % 15 == 0 or completed_count == len(tasks):
                    print(f"    Progress: {completed_count}/{len(tasks)} runs completed ({completed_count * 100 // len(tasks)}%)")
            except Exception as e:
                print(f"[!] Task {task} failed: {e}")

    save_summary_csv(results)
    plot_results(results)
    print("[✓] Lab 3 Task 1 evaluation completed successfully!")


if __name__ == "__main__":
    main()
