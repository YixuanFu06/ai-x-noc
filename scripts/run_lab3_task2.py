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
DATA_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/data/lab3_task2")
FIGURES_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/reports/figures")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# 10,000 clock cycles at 1GHz (1000 ps/cycle)
CLOCK_PERIOD_TICKS = 1000
ACTUAL_CYCLES = 10000
SIM_CYCLES_TICKS = ACTUAL_CYCLES * CLOCK_PERIOD_TICKS
NUM_CPUS = 16
NUM_DIRS = 16
MESH_ROWS = 4

INJECTION_RATES = [
    0.01, 0.03, 0.05, 0.08, 0.10,
    0.12, 0.15, 0.18, 0.20, 0.25,
    0.30, 0.35, 0.40, 0.45, 0.50
]

# Three flow-control / buffer configurations
CONFIGURATIONS = [
    {"name": "VC=1, Depth=1", "vcs": 1, "wormhole": False},
    {"name": "VC=16, Depth=1", "vcs": 16, "wormhole": False},
    {"name": "VC=1, Depth=16 (Wormhole)", "vcs": 1, "wormhole": True},
]

TRAFFIC_PATTERNS = ["uniform_random", "tornado"]


def run_simulation(args):
    config_name, vcs, wormhole, traffic, rate = args
    cfg_tag = config_name.replace(" ", "_").replace("=", "").replace(",", "_").replace("(", "").replace(")", "")
    out_dir = os.path.join(DATA_DIR, cfg_tag, traffic, f"inj_{rate:.3f}")
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
        "--routing-algorithm=1",
        "--inj-vnet=0",
        f"--synthetic={traffic}",
        f"--sim-cycles={SIM_CYCLES_TICKS}",
        f"--injectionrate={rate:.3f}",
        f"--vcs-per-vnet={vcs}"
    ]
    if wormhole:
        cmd.append("--wormhole")
        
    log_file = os.path.join(out_dir, "run.log")
    with open(log_file, "w") as f:
        res = subprocess.run(cmd, cwd=GEM5_DIR, stdout=f, stderr=subprocess.STDOUT)
        
    stats_file = os.path.join(out_dir, "stats.txt")
    data = parse_stats(stats_file, config_name, vcs, wormhole, traffic, rate)

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


def parse_stats(stats_file, config_name, vcs, wormhole, traffic, rate):
    metrics = {
        "config_name": config_name,
        "vcs_per_vnet": vcs,
        "wormhole_enabled": wormhole,
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
        print(f"Warning: {stats_file} not found for {config_name}-{traffic} at rate {rate}")
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
    csv_file = os.path.join(DATA_DIR, "summary_lab3_task2.csv")
    fieldnames = [
        "config_name", "vcs_per_vnet", "wormhole_enabled",
        "traffic_pattern", "injection_rate",
        "packets_injected", "packets_received",
        "avg_queueing_latency_ticks", "avg_network_latency_ticks",
        "avg_packet_latency_ticks", "avg_packet_latency_cycles",
        "avg_hops", "reception_rate", "avg_link_utilization"
    ]
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda x: (x["config_name"], x["traffic_pattern"], x["injection_rate"])):
            writer.writerow(row)
    print(f"[✓] Summary CSV saved to: {csv_file}")


def plot_results(results):
    cfg_colors = {
        "VC=1, Depth=1": "#d62728",
        "VC=16, Depth=1": "#2ca02c",
        "VC=1, Depth=16 (Wormhole)": "#1f77b4"
    }
    cfg_markers = {
        "VC=1, Depth=1": "x",
        "VC=16, Depth=1": "s",
        "VC=1, Depth=16 (Wormhole)": "o"
    }

    # Plot for each traffic pattern
    for traffic in TRAFFIC_PATTERNS:
        plt.figure(figsize=(9, 6), dpi=300)
        for cfg in CONFIGURATIONS:
            name = cfg["name"]
            pts = [r for r in results if r["config_name"] == name and r["traffic_pattern"] == traffic]
            pts.sort(key=lambda x: x["reception_rate"])
            x = [p["reception_rate"] for p in pts]
            y = [p["avg_packet_latency_cycles"] for p in pts]
            plt.plot(x, y, label=name, color=cfg_colors[name],
                     marker=cfg_markers[name], linewidth=2, markersize=6)

        plt.title(f"Buffer Allocation Comparison ({traffic.replace('_', ' ').title()}, 16-Node 4x4 Mesh)",
                  fontsize=13, fontweight="bold", pad=12)
        plt.xlabel("Throughput / Reception Rate (packets/node/cycle)", fontsize=11)
        plt.ylabel("Average Packet Latency (Cycles)", fontsize=11)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend(fontsize=10, frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, f"lab3_task2_comparison_{traffic}.png"))
        plt.savefig(os.path.join(FIGURES_DIR, f"lab3_task2_comparison_{traffic}.pdf"))
        plt.close()

    # Combined 2-panel plot (Uniform Random and Tornado)
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5), dpi=300)
    for idx, traffic in enumerate(["uniform_random", "tornado"]):
        for cfg in CONFIGURATIONS:
            name = cfg["name"]
            pts = [r for r in results if r["config_name"] == name and r["traffic_pattern"] == traffic]
            pts.sort(key=lambda x: x["reception_rate"])
            x = [p["reception_rate"] for p in pts]
            y = [p["avg_packet_latency_cycles"] for p in pts]
            axes[idx].plot(x, y, label=name, color=cfg_colors[name],
                           marker=cfg_markers[name], linewidth=2, markersize=5)
                           
        title_tag = "(a) Uniform Random Traffic" if idx == 0 else "(b) Tornado Traffic"
        axes[idx].set_title(title_tag, fontsize=12, fontweight="bold")
        axes[idx].set_xlabel("Throughput (packets/node/cycle)", fontsize=11)
        axes[idx].set_ylabel("Average Latency (Cycles)", fontsize=11)
        axes[idx].grid(True, linestyle="--", alpha=0.6)
        axes[idx].legend(fontsize=10)

    plt.suptitle("Lab 3 Task 2: Buffer Depth vs. Virtual Channels Trade-Off (16-Node 4x4 Mesh)",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    comb_file = os.path.join(FIGURES_DIR, "lab3_task2_combined_buffer_analysis.png")
    plt.savefig(comb_file, bbox_inches="tight")
    plt.savefig(os.path.join(FIGURES_DIR, "lab3_task2_combined_buffer_analysis.pdf"), bbox_inches="tight")
    plt.close()
    print(f"[✓] Combined figure saved to: {comb_file}")


def main():
    tasks = []
    for cfg in CONFIGURATIONS:
        for traffic in TRAFFIC_PATTERNS:
            for rate in INJECTION_RATES:
                tasks.append((cfg["name"], cfg["vcs"], cfg["wormhole"], traffic, rate))

    print(f"[*] Total simulation runs for Task 2: {len(tasks)}")
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
    print("[✓] Lab 3 Task 2 evaluation completed successfully!")


if __name__ == "__main__":
    main()
