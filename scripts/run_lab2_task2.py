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
DATA_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/data/lab2_task2")
FIGURES_DIR = os.path.join(WORKSPACE_ROOT, "ai-x-noc/reports/figures")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# 10,000 clock cycles at 1GHz (1000 ps/cycle)
CLOCK_PERIOD_TICKS = 1000
ACTUAL_CYCLES = 10000
SIM_CYCLES_TICKS = ACTUAL_CYCLES * CLOCK_PERIOD_TICKS
NUM_CPUS = 64
NUM_DIRS = 64
MESH_ROWS = 8

INJECTION_RATES = [
    0.01, 0.03, 0.05, 0.08, 0.10,
    0.15, 0.20, 0.25, 0.30, 0.35,
    0.40, 0.45, 0.50
]

SWEEP_VCS = [1, 2, 4, 8, 16]
SWEEP_ROUTER_LATENCY = [1, 2, 3, 4]
SWEEP_LINK_WIDTH = [32, 64, 128, 256]


def run_simulation(args):
    sweep_type, param_val, rate, vcs, router_lat, link_width = args
    out_dir = os.path.join(DATA_DIR, sweep_type, f"val_{param_val}", f"inj_{rate:.3f}")
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
        "--synthetic=uniform_random",
        f"--sim-cycles={SIM_CYCLES_TICKS}",
        f"--injectionrate={rate:.3f}",
        f"--vcs-per-vnet={vcs}",
        f"--router-latency={router_lat}",
        f"--link-width-bits={link_width}"
    ]
    
    log_file = os.path.join(out_dir, "run.log")
    with open(log_file, "w") as f:
        res = subprocess.run(cmd, cwd=GEM5_DIR, stdout=f, stderr=subprocess.STDOUT)
        
    stats_file = os.path.join(out_dir, "stats.txt")
    data = parse_stats(stats_file, sweep_type, param_val, rate, vcs, router_lat, link_width)

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


def parse_stats(stats_file, sweep_type, param_val, rate, vcs, router_lat, link_width):
    metrics = {
        "sweep_type": sweep_type,
        "param_value": param_val,
        "injection_rate": rate,
        "vcs_per_vnet": vcs,
        "router_latency": router_lat,
        "link_width_bits": link_width,
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
        print(f"Warning: {stats_file} not found")
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


def save_csv(data_list, filename):
    csv_file = os.path.join(DATA_DIR, filename)
    fieldnames = [
        "sweep_type", "param_value", "injection_rate",
        "vcs_per_vnet", "router_latency", "link_width_bits",
        "packets_injected", "packets_received",
        "avg_queueing_latency_ticks", "avg_network_latency_ticks",
        "avg_packet_latency_ticks", "avg_packet_latency_cycles",
        "avg_hops", "reception_rate", "avg_link_utilization"
    ]
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(data_list, key=lambda x: (x["param_value"], x["injection_rate"])):
            writer.writerow(row)
    print(f"[✓] CSV saved to: {csv_file}")


def plot_single_sweep(data_list, param_name, title_name, fig_prefix, unit_label=""):
    # Group by param_value
    grouped = {}
    for d in data_list:
        val = d["param_value"]
        if val not in grouped:
            grouped[val] = []
        grouped[val].append(d)
        
    for val in grouped:
        grouped[val].sort(key=lambda x: x["injection_rate"])
        
    cmap = plt.get_cmap("tab10")
    markers = ["o", "s", "^", "D", "v", "P"]

    # 1. Latency vs Throughput
    plt.figure(figsize=(8.5, 5.5), dpi=300)
    for idx, (val, pts) in enumerate(sorted(grouped.items())):
        x = [p["reception_rate"] for p in pts]
        y = [p["avg_packet_latency_cycles"] for p in pts]
        label = f"{param_name} = {val} {unit_label}".strip()
        plt.plot(x, y, marker=markers[idx % len(markers)], label=label,
                 color=cmap(idx), linewidth=2, markersize=6)
                 
    plt.title(f"Impact of {title_name} on Latency-Throughput (8x8 Mesh)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Throughput / Reception Rate (packets/node/cycle)", fontsize=11)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=10, frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, f"{fig_prefix}_latency_throughput.png"))
    plt.savefig(os.path.join(FIGURES_DIR, f"{fig_prefix}_latency_throughput.pdf"))
    plt.close()

    # 2. Latency vs Injection Rate
    plt.figure(figsize=(8.5, 5.5), dpi=300)
    for idx, (val, pts) in enumerate(sorted(grouped.items())):
        x = [p["injection_rate"] for p in pts]
        y = [p["avg_packet_latency_cycles"] for p in pts]
        label = f"{param_name} = {val} {unit_label}".strip()
        plt.plot(x, y, marker=markers[idx % len(markers)], label=label,
                 color=cmap(idx), linewidth=2, markersize=6)
                 
    plt.title(f"Impact of {title_name} on Latency vs. Injection Rate", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Injection Rate (packets/node/cycle)", fontsize=11)
    plt.ylabel("Average Packet Latency (Cycles)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=10, frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, f"{fig_prefix}_latency_vs_injrate.png"))
    plt.savefig(os.path.join(FIGURES_DIR, f"{fig_prefix}_latency_vs_injrate.pdf"))
    plt.close()


def plot_combined_figure(vcs_data, rlat_data, lwidth_data):
    fig, axes = plt.subplots(1, 3, figsize=(20, 5.5), dpi=300)
    cmap = plt.get_cmap("tab10")
    markers = ["o", "s", "^", "D", "v"]

    # Subplot 1: VCs
    grouped_vcs = {}
    for d in vcs_data:
        val = d["param_value"]
        grouped_vcs.setdefault(val, []).append(d)
    for idx, (val, pts) in enumerate(sorted(grouped_vcs.items())):
        pts.sort(key=lambda x: x["reception_rate"])
        axes[0].plot([p["reception_rate"] for p in pts], [p["avg_packet_latency_cycles"] for p in pts],
                     marker=markers[idx % len(markers)], label=f"VCs = {val}", color=cmap(idx), linewidth=2)
    axes[0].set_title("(a) Virtual Channels (vcs-per-vnet)", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Throughput (pkts/node/cycle)", fontsize=11)
    axes[0].set_ylabel("Latency (Cycles)", fontsize=11)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(fontsize=9)

    # Subplot 2: Router Latency
    grouped_rlat = {}
    for d in rlat_data:
        val = d["param_value"]
        grouped_rlat.setdefault(val, []).append(d)
    for idx, (val, pts) in enumerate(sorted(grouped_rlat.items())):
        pts.sort(key=lambda x: x["reception_rate"])
        axes[1].plot([p["reception_rate"] for p in pts], [p["avg_packet_latency_cycles"] for p in pts],
                     marker=markers[idx % len(markers)], label=f"Router Latency = {val} cyc", color=cmap(idx), linewidth=2)
    axes[1].set_title("(b) Router Pipeline Latency", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Throughput (pkts/node/cycle)", fontsize=11)
    axes[1].set_ylabel("Latency (Cycles)", fontsize=11)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(fontsize=9)

    # Subplot 3: Link Width
    grouped_lwidth = {}
    for d in lwidth_data:
        val = d["param_value"]
        grouped_lwidth.setdefault(val, []).append(d)
    for idx, (val, pts) in enumerate(sorted(grouped_lwidth.items())):
        pts.sort(key=lambda x: x["reception_rate"])
        axes[2].plot([p["reception_rate"] for p in pts], [p["avg_packet_latency_cycles"] for p in pts],
                     marker=markers[idx % len(markers)], label=f"Link Width = {val} bits", color=cmap(idx), linewidth=2)
    axes[2].set_title("(c) Physical Link Width", fontsize=12, fontweight="bold")
    axes[2].set_xlabel("Throughput (pkts/node/cycle)", fontsize=11)
    axes[2].set_ylabel("Latency (Cycles)", fontsize=11)
    axes[2].grid(True, linestyle="--", alpha=0.6)
    axes[2].legend(fontsize=9)

    plt.suptitle("Lab 2 Task 2: Microarchitectural Sensitivity Analysis (8x8 Mesh, uniform_random)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    comb_file = os.path.join(FIGURES_DIR, "lab2_task2_combined_analysis.png")
    plt.savefig(comb_file, bbox_inches="tight")
    plt.savefig(os.path.join(FIGURES_DIR, "lab2_task2_combined_analysis.pdf"), bbox_inches="tight")
    plt.close()
    print(f"[✓] Combined figure saved to: {comb_file}")


def main():
    tasks = []

    # 1. Sweep VCs (Default: router_lat=1, link_width=128)
    for vcs in SWEEP_VCS:
        for rate in INJECTION_RATES:
            tasks.append(("sweep_vcs", vcs, rate, vcs, 1, 128))

    # 2. Sweep Router Latency (Default: vcs=4, link_width=128)
    for rlat in SWEEP_ROUTER_LATENCY:
        for rate in INJECTION_RATES:
            tasks.append(("sweep_router_latency", rlat, rate, 4, rlat, 128))

    # 3. Sweep Link Width (Default: vcs=4, router_lat=1)
    for lwidth in SWEEP_LINK_WIDTH:
        for rate in INJECTION_RATES:
            tasks.append(("sweep_link_width", lwidth, rate, 4, 1, lwidth))

    print(f"[*] Total Task 2 simulation runs: {len(tasks)}")
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

    # Partition results
    vcs_data = [r for r in results if r["sweep_type"] == "sweep_vcs"]
    rlat_data = [r for r in results if r["sweep_type"] == "sweep_router_latency"]
    lwidth_data = [r for r in results if r["sweep_type"] == "sweep_link_width"]

    # Save CSVs
    save_csv(vcs_data, "summary_sweep_vcs.csv")
    save_csv(rlat_data, "summary_sweep_router_latency.csv")
    save_csv(lwidth_data, "summary_sweep_link_width.csv")

    # Generate individual plots
    plot_single_sweep(vcs_data, "VCs", "Virtual Channel Count", "lab2_task2_vcs")
    plot_single_sweep(rlat_data, "Router Latency", "Router Pipeline Latency", "lab2_task2_router_latency", "cycles")
    plot_single_sweep(lwidth_data, "Link Width", "Physical Link Width", "lab2_task2_link_width", "bits")

    # Generate combined 3-panel figure
    plot_combined_figure(vcs_data, rlat_data, lwidth_data)

    print("[✓] Lab 2 Task 2 finished successfully!")


if __name__ == "__main__":
    main()
