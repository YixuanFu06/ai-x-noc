# ai-x-noc: Network-on-Chip (NoC) Labs

This repository contains the complete lab assignments and research implementations for the **AI & X** course, built upon the **gem5 simulator** (v23.0.0.1) and its **Garnet 3.0** on-chip interconnection network model.

---

## 📂 Repository Structure

```text
ai-x-noc/
├── data/                         # Consolidated experimental datasets (CSV format)
│   ├── lab2_task1/               # Lab 2 Task 1: Traffic pattern sweeps
│   ├── lab2_task2/               # Lab 2 Task 2: Microarchitectural sweeps (VCs, latency, width)
│   ├── lab3_task1/               # Lab 3 Task 1: 16-node Ring vs. 4x4 Mesh sweeps
│   └── lab3_task2/               # Lab 3 Task 2: Buffer depth vs. VCs flow-control sweeps
│
├── reports/                      # Detailed markdown reports & figures
│   ├── Lab1_Report.md            # Lab 1: Mechanics, Statistics & Theoretical Q&A
│   ├── Lab2_Report.md            # Lab 2: Performance Analysis & Latency Bottlenecks
│   ├── Lab3_Report.md            # Lab 3: Topology Design & Wormhole Flow Control
│   └── figures/                  # High-resolution generated plots (PNG & vector PDF)
│
├── scripts/                      # Automated multi-process simulation and plotting scripts
│   ├── extract_network_stats.sh  # Statistical extraction script for Lab 1
│   ├── run_lab2_task1.py         # Multi-threaded sweep for Lab 2 Task 1 (95 runs)
│   ├── run_lab2_task2.py         # Multi-threaded sweep for Lab 2 Task 2 (169 runs)
│   ├── run_lab3_task1.py         # Multi-threaded sweep for Lab 3 Task 1 (120 runs)
│   └── run_lab3_task2.py         # Multi-threaded sweep for Lab 3 Task 2 (90 runs)
│
├── src_modified/                 # Custom / modified source code (symlinked into gem5)
│   ├── configs/
│   │   ├── network/Network.py    # Added --wormhole CLI flag support
│   │   └── topologies/Ring.py    # 16-node bidirectional 1D Ring topology
│   └── src/mem/ruby/network/garnet/
│       ├── GarnetNetwork.hh/.cc  # Stat units & wormhole depth=16 buffer initialization
│       ├── GarnetNetwork.py      # SimObject wormhole parameter definition
│       ├── InputUnit.hh/.cc      # Multi-packet deep buffering in active VCs
│       ├── OutputUnit.hh/.cc     # Credit-based free VC arbitration
│       ├── OutVcState.hh/.cc     # Credit tracking and VC state management
│       ├── RoutingUnit.hh/.cc    # Shortest-path routing on bidirectional Ring
│       └── SwitchAllocator.hh/.cc# Wormhole single-flit routing & credit turnaround
│
└── README.md
```

---

## 🛠️ Environment Setup & Building gem5

### 1. Prerequisites

Install required build dependencies (Ubuntu / Debian / WSL):
```bash
sudo apt update
sudo apt install -y build-essential git m4 scons zlib1g zlib1g-dev \
    libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
    python3-dev python3-pip libboost-all-dev pkg-config
```

### 2. Symlink Modified Files to gem5

Clone `gem5` (v23.0.0.1) side-by-side with `ai-x-noc`, and link our modified files:
```bash
# From workspace root directory containing both gem5/ and ai-x-noc/
cd gem5

# Symlink all modified configuration and source files
ln -sf $(pwd)/../ai-x-noc/src_modified/configs/topologies/Ring.py configs/topologies/Ring.py
ln -sf $(pwd)/../ai-x-noc/src_modified/configs/network/Network.py configs/network/Network.py

for file in GarnetNetwork.cc GarnetNetwork.hh GarnetNetwork.py \
            InputUnit.cc InputUnit.hh OutputUnit.cc OutputUnit.hh \
            OutVcState.cc OutVcState.hh RoutingUnit.cc RoutingUnit.hh \
            SwitchAllocator.cc SwitchAllocator.hh; do
    ln -sf $(pwd)/../ai-x-noc/src_modified/src/mem/ruby/network/garnet/$file \
           src/mem/ruby/network/garnet/$file
done
```

### 3. Compiling gem5 (Garnet Standalone)

Compile gem5 with standalone Garnet network support:
```bash
cd gem5
scons build/NULL/gem5.opt PROTOCOL=Garnet_standalone -j$(nproc)
```

---

## 🔬 Completed Labs Overview & Usage

### 📘 Lab 1: Running Synthetic Traffic & Statistics
* **Objective:** Learn basic Garnet operation, inject synthetic traffic, configure clock frequency (1GHz vs. 2GHz), complete statistical units in C++ source code, and implement automated metric extraction (`Reception Rate`).
* **Key Command / Script:**
  ```bash
  # Single run test
  ./build/NULL/gem5.opt configs/example/garnet_synth_traffic.py \
      --network=garnet --num-cpus=64 --num-dirs=64 \
      --topology=Mesh_XY --mesh-rows=8 \
      --inj-vnet=0 --synthetic=uniform_random \
      --sim-cycles=10000000 --injectionrate=0.01

  # Extract statistics and calculate reception rate
  bash ../ai-x-noc/scripts/extract_network_stats.sh 64 10000 m5out/stats.txt
  ```
* **Full Report:** [reports/Lab1_Report.md](file:///z:/home/yixuanfu/2026Summer/AI_and_X/Lab/ai-x-noc/reports/Lab1_Report.md)

---

### 📗 Lab 2: Network Performance & Sensitivity Analysis
* **Objective:**
  1. **Task 1 (Traffic Patterns):** Sweep 5 synthetic traffic patterns (`uniform_random`, `neighbor`, `transpose`, `tornado`, `shuffle`) across 19 injection rates ($0.01 \sim 0.50$) on an 8×8 Mesh for 10,000 cycles.
  2. **Task 2 (Microarchitectural Exploration):** Evaluate sensitivity to Virtual Channels (`vcs-per-vnet` $\in \{1, 2, 4, 8, 16\}$), Router Latency (`router-latency` $\in \{1, 2, 3, 4\}$), and Link Width (`link-width-bits` $\in \{32, 64, 128, 256\}$).
  3. **Task 3 (Theory & Analysis):** Latency component decomposition, bottleneck analysis across load regimes, and credit-based flow control mechanisms.
* **Running Automated Sweeps:**
  ```bash
  # Run Task 1 (95 parallel simulation runs + plots generation)
  python3 ../ai-x-noc/scripts/run_lab2_task1.py

  # Run Task 2 (169 parallel simulation runs + 3-panel plots generation)
  python3 ../ai-x-noc/scripts/run_lab2_task2.py
  ```
* **Output Data & Figures:**
  * Datasets: `data/lab2_task1/summary_lab2_task1.csv`, `data/lab2_task2/summary_lab2_task2_*.csv`
  * Plots: `reports/figures/lab2_task1_*.png`, `reports/figures/lab2_task2_combined_analysis.png`
* **Full Report:** [reports/Lab2_Report.md](file:///z:/home/yixuanfu/2026Summer/AI_and_X/Lab/ai-x-noc/reports/Lab2_Report.md)

---

### 📙 Lab 3: Topology Design & Wormhole Flow Control
* **Objective:**
  1. **Task 1 (Ring Topology & Shortest Path Routing):**
     * Implemented 16-node bidirectional 1D Ring topology ([Ring.py](file:///z:/home/yixuanfu/2026Summer/AI_and_X/Lab/ai-x-noc/src_modified/configs/topologies/Ring.py)).
     * Implemented custom shortest-path ring routing algorithm in `RoutingUnit::outportComputeCustom()`:
       $$d_{\text{cw}} = (dest - src + N) \pmod N,\quad d_{\text{ccw}} = (src - dest + N) \pmod N$$
     * Evaluated and compared 16-node Ring vs. 16-node 4×4 Mesh.
  2. **Task 2 (Wormhole Flow Control & Buffer Dimension Trade-off):**
     * Implemented `--wormhole` flow-control in Garnet with deep buffer capacity (Depth = 16) per virtual channel.
     * Modified `InputUnit`, `OutputUnit`, and `SwitchAllocator` to allow up to 16 single-flit packets to buffer in a single VC with dynamic credit recycling.
     * Conducted 3-way comparative evaluation under identical buffering budget:
       - **Config 1:** `VC = 1, Depth = 1` (Baseline, extreme HoL blocking)
       - **Config 2:** `VC = 16, Depth = 1` (Multi-VC, eliminates HoL blocking, high arbiter area)
       - **Config 3:** `VC = 1, Depth = 16 (Wormhole)` (Deep single FIFO, area-efficient compromise)
* **Running Automated Sweeps:**
  ```bash
  # Run Lab 3 Task 1 (120 simulation runs: Ring across 5 patterns + Mesh baseline)
  python3 ../ai-x-noc/scripts/run_lab3_task1.py

  # Run Lab 3 Task 2 (90 simulation runs: 3 buffer configurations across injection rates)
  python3 ../ai-x-noc/scripts/run_lab3_task2.py
  ```
* **Output Data & Figures:**
  * Datasets: `data/lab3_task1/summary_lab3_task1.csv`, `data/lab3_task2/summary_lab3_task2.csv`
  * Plots: `reports/figures/lab3_task1_ring_vs_mesh_comparison.png`, `reports/figures/lab3_task2_combined_buffer_analysis.png`
* **Full Report:** [reports/Lab3_Report.md](file:///z:/home/yixuanfu/2026Summer/AI_and_X/Lab/ai-x-noc/reports/Lab3_Report.md)

---

## 📊 Summary of Key Architectural Insights

| Aspect | Key Findings & Architectural Trade-offs |
| :--- | :--- |
| **Clock Frequency & Timing (Lab 1)** | gem5 event-driven engine models time in discrete **Ticks** ($1\text{ ps}$). A $10,000\text{ cycle}$ simulation at $1\text{ GHz}$ corresponds to $10,000,000\text{ Ticks}$. |
| **Traffic Patterns & Locality (Lab 2)** | Nearest-neighbor traffic achieves highest throughput due to 1-hop locality; permutation traffic (`shuffle`, `transpose`, `tornado`) stresses bisection links and saturates early. |
| **Microarchitecture Sensitivity (Lab 2)** | Increasing VCs alleviates Head-of-Line blocking; increasing link width reduces multi-flit serialization latency; pipeline stages shift zero-load baseline vertically. |
| **Ring vs. Mesh Topology (Lab 3)** | 16-node Ring has higher average hops ($4.00$ vs $2.50$) and narrower bisection bandwidth (4 vs 8 links) compared to 4×4 Mesh, saturating earlier but using simpler 3-port routers. |
| **VC Dimension vs. Buffer Depth (Lab 3)** | Under the same 16-flit buffer budget, `VC=16, Depth=1` achieves highest throughput ($>0.50$) by eliminating inter-VC HoL blocking, while `VC=1, Depth=16 (Wormhole)` achieves $+53.7\%$ throughput over baseline at minimal router arbiter area. |
