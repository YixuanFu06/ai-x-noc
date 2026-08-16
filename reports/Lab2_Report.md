# Lab 2 Report: Performance Analysis of NoC

**Course:** Network-on-Chip (NoC) / Computer Architecture  
**Author:** Yixuan Fu  
**Date:** August 2026  
**Environment:** gem5 v23.0.0.1 (Garnet 3.0 Standalone, Ubuntu 20.04 on WSL)

---

## 1. Task 1: Traffic Patterns & Latency-Throughput Analysis

### 1.1 Experimental Setup
* **Topology:** 8×8 Mesh (`Mesh_XY`), 64 CPUs, 64 Directories.
* **Traffic Patterns:** `uniform_random`, `neighbor`, `transpose`, `tornado`, `shuffle`.
* **Injection Rate Range:** $0.01 \sim 0.50$ (19 non-uniform sampling points).
* **Simulation Duration:** 10,000 clock cycles ($10,000,000$ Ticks at 1 GHz).
* **Automated Script:** `ai-x-noc/scripts/run_lab2_task1.py` (executed with 16 parallel workers).

### 1.2 Quantitative Results Summary

The extracted metrics from `ai-x-noc/data/lab2_task1/summary_lab2_task1.csv` are summarized below:

| Traffic Pattern | Zero-load Latency (Cycles) | Avg Hops | Saturation Injection Rate | Peak Throughput (pkts/node/cycle) |
| :--- | :---: | :---: | :---: | :---: |
| **`neighbor`** | **4.25** | **1.75** | **> 0.50** (No saturation observed) | **0.499** |
| **`tornado`** | **6.25** | **3.75** | **~ 0.45** | **0.498** |
| **`shuffle`** | **6.50** | **4.00** | **~ 0.40** | **0.468** |
| **`transpose`** | **7.80** | **5.25** | **~ 0.28** (Earliest saturation) | **0.405** |
| **`uniform_random`** | **7.78** | **5.26** | **> 0.50** (High capacity) | **0.499** |

---

### 1.3 Latency-Throughput Curves & Visualizations

The generated evaluation curves are located in `ai-x-noc/reports/figures/`:
1. **Latency vs. Throughput Curve**: `figures/lab2_task1_latency_throughput.png`
2. **Latency vs. Injection Rate Curve**: `figures/lab2_task1_latency_vs_injrate.png`
3. **Throughput vs. Injection Rate Curve**: `figures/lab2_task1_throughput_vs_injrate.png`

---

### 1.4 Detailed Performance Analysis

1. **Zero-Load Latency (Low-Load Regime):**
   * Under low injection rates ($\text{rate} \le 0.05$), queueing delay is negligible ($\approx 1\text{ Cycle}$), and packet latency is dominated by **network hop traversal delay**:
     $$\text{Zero-load Latency} \approx \text{Head Queue Delay} + \text{Avg Hops} \times (\text{Router Latency} + \text{Link Latency})$$
   * `neighbor` has the minimum average hops ($1.75$), resulting in the lowest zero-load latency ($4.25\text{ Cycles}$).
   * `uniform_random` and `transpose` have the highest average hops ($5.25 \sim 5.26$), leading to the highest zero-load latency ($\approx 7.8\text{ Cycles}$).

2. **Saturation Points & Network Throughput:**
   * **`transpose` saturates earliest ($\sim 0.28$)**: In XY routing, $(x, y) \to (y, x)$ maps traffic along the sub-diagonals, creating severe bottleneck hotspots on center bisection links while leaving other links underutilized.
   * **`shuffle` saturates around $0.40$**: Binary cyclic shift creates unequal distance communication, causing buffer accumulation at intermediate switching nodes.
   * **`tornado` begins congesting around $0.45$**: Unidirectional half-network traversal heavily loads horizontal links.
   * **`neighbor` & `uniform_random` maintain high throughput ($> 0.50$)**:
     - `neighbor` traffic is strictly localized (1-hop distance), producing virtually zero link contention.
     - `uniform_random` evenly distributes traffic over all 64 nodes and all bisection links, maximizing global network capacity without localized hot spots.

---

## 2. Task 2: Microarchitectural Sensitivity Analysis

In this task, we fixed the workload to `uniform_random` on the 8×8 Mesh and performed sensitivity sweeps on three fundamental hardware microarchitectural parameters:
1. **Virtual Channels (`--vcs-per-vnet`)**: $\{1, 2, 4, 8, 16\}$
2. **Router Pipeline Latency (`--router-latency`)**: $\{1, 2, 3, 4\}\text{ cycles}$
3. **Physical Link Width (`--link-width-bits`)**: $\{32, 64, 128, 256\}\text{ bits}$

The automated sweep script `ai-x-noc/scripts/run_lab2_task2.py` executed all 169 simulation runs in parallel.

---

### 2.1 Virtual Channels Sensitivity Sweep (`vcs-per-vnet`)

| VCs per VNet | Zero-Load Latency (Cycles) | Saturation Injection Rate | Saturation Peak Throughput (pkts/node/cycle) | Architectural Observations |
| :---: | :---: | :---: | :---: | :--- |
| **`VC = 1`** | **7.86** | **~ 0.10** | **0.138** | **Severe Head-of-Line (HoL) Blocking.** Packets blocked behind busy downstream buffers choke the entire input port, causing premature network saturation. |
| **`VC = 2`** | **7.78** | **~ 0.30** | **0.326** | Partial HoL mitigation. Capacity increases by $> 2.3\times$ compared to $VC=1$. |
| **`VC = 4`** | **7.78** | **> 0.50** | **0.499** | Full pipeline buffering. No saturation observed below rate 0.50. |
| **`VC = 8`** | **7.78** | **> 0.50** | **0.499** | Marginal latency reduction at high load; law of diminishing returns for uniform traffic. |
| **`VC = 16`** | **7.78** | **> 0.50** | **0.499** | Excess buffer capacity; area overhead outweighs performance gains. |

**Key Takeaway:** Increasing VCs from 1 to 4 provides dramatic throughput gains by eliminating HoL blocking. Beyond $VC=4$, additional VCs provide diminishing returns for benign uniform random traffic.

---

### 2.2 Router Pipeline Latency Sensitivity Sweep (`router-latency`)

| Router Latency | Zero-Load Latency (Cycles) | Latency Increase ($\Delta$) | Expected Theoretical Increase ($\text{Avg Hops} \times \Delta$) |
| :---: | :---: | :---: | :---: |
| **`1 Cycle`** (Single-stage) | **7.78** | Baseline | Baseline |
| **`2 Cycles`** (2-stage) | **13.04** | **+ 5.26 Cycles** | $5.26 \times 1 = \mathbf{5.26\text{ Cycles}}$ (Exact match) |
| **`3 Cycles`** (3-stage) | **18.30** | **+ 10.52 Cycles** | $5.26 \times 2 = \mathbf{10.52\text{ Cycles}}$ (Exact match) |
| **`4 Cycles`** (4-stage) | **23.56** | **+ 15.78 Cycles** | $5.26 \times 3 = \mathbf{15.78\text{ Cycles}}$ (Exact match) |

**Key Takeaway:** Router pipeline latency acts as an additive penalty per hop. The entire latency curve shifts rigidly upward by $\Delta \text{Latency} = \text{Avg Hops} \times \Delta \text{router\_latency}$.

---

### 2.3 Physical Link Width Sensitivity Sweep (`link-width-bits`)

| Link Width | Flit Size | Flits per Control Pkt (64-bit) | Zero-Load Latency (Cycles) | Saturation Rate |
| :---: | :---: | :---: | :---: | :---: |
| **`32 bits`** | 32 bits | **2 Flits** (Serialization penalty) | **13.04** | **~ 0.30** |
| **`64 bits`** | 64 bits | **1 Flit** | **7.78** | **> 0.50** |
| **`128 bits`** | 128 bits | **1 Flit** | **7.78** | **> 0.50** |
| **`256 bits`** | 256 bits | **1 Flit** | **7.78** | **> 0.50** |

**Key Takeaway:** Narrow links ($32\text{ bits}$) force packets to undergo multi-flit serialization, doubling hop link traversal time and halving network saturation throughput. For 64-bit control packets, widening the link beyond 64 bits maintains 1-flit transport.

---

### 2.4 Visualizations
The generated plots in `ai-x-noc/reports/figures/` illustrate these microarchitectural trade-offs:
* **Combined 3-Panel Analysis**: `figures/lab2_task2_combined_analysis.png`
* **VCs Sweep**: `figures/lab2_task2_vcs_latency_throughput.png`
* **Router Latency Sweep**: `figures/lab2_task2_router_latency_latency_throughput.png`
* **Link Width Sweep**: `figures/lab2_task2_link_width_latency_throughput.png`

---

## 3. Task 3: Questions & Detailed Answers

### Q1: What are the components of network latency? Which component is dominant/bottleneck (for different traffic patterns/loads/linkwidths)?

#### 1. Components of Network Latency
The total end-to-end packet latency ($T_{\text{total}}$) from packet generation at the source to complete consumption at the destination is composed of three primary parts:

$$T_{\text{total}} = T_{\text{src\_queue}} + T_{\text{network\_traversal}} + T_{\text{serialization}}$$

1. **Source Queueing Latency ($T_{\text{src\_queue}}$)**:
   * The time a packet spends buffered inside the source Network Interface (NI) waiting for an available Virtual Channel / Credit before it can enter the network.
2. **Network Traversal Latency ($T_{\text{network\_traversal}}$)**:
   * The time taken for the packet's **head flit** to traverse $H$ hops from the source router to the destination router:
     $$T_{\text{network\_traversal}} = \sum_{i=1}^H \left( t_{\text{router}, i} + t_{\text{link}, i} + t_{\text{contention}, i} \right)$$
     - $t_{\text{router}}$: Router pipeline stage delay (Buffer Write + Route Compute + VC Allocation + Switch Allocation + Crossbar Traversal).
     - $t_{\text{link}}$: Physical channel/wire transit delay across links.
     - $t_{\text{contention}}$: Dynamic blocking delay caused by port contention, switch arbitration loss, or lack of downstream credits.
3. **Serialization Latency ($T_{\text{serialization}}$)**:
   * The time required for the remaining body and tail flits of the packet to follow the head flit across physical channels:
     $$T_{\text{serialization}} = \left( \left\lceil \frac{\text{Packet Size (bits)}}{\text{Link Width (bits)}} \right\rceil - 1 \right) \times t_{\text{cycle}}$$

---

#### 2. Dominant Components / Bottlenecks under Different Scenarios

* **Low-Load Regime ($\text{Injection Rate} \le 0.05$)**:
   * **Dominant Component**: **Zero-Load Hop Traversal Latency ($H \times (t_{\text{router}} + t_{\text{link}})$)**.
   * *Reason*: Queues are empty ($T_{\text{src\_queue}} \approx 1\text{ Cycle}$) and link contention is negligible ($t_{\text{contention}} \approx 0$). Latency is strictly determined by geometric topological distance (average hops).

* **High-Load / Post-Saturation Regime ($\text{Injection Rate} \ge \text{Saturation Point}$)**:
   * **Dominant Component**: **Source Queueing Latency ($T_{\text{src\_queue}}$) and Router Backpressure Contention ($t_{\text{contention}}$)**.
   * *Reason*: Buffers fill up, creating backpressure trees that stall upstream routers. Packets spend hundreds to thousands of cycles waiting in NI buffers before being injected ($> 99\%$ of total latency).

* **Asymmetric / Adversarial Traffic Patterns (`transpose`, `tornado`, `shuffle`)**:
   * **Dominant Component**: **Router Contention Delay ($t_{\text{contention}}$) at Hotspot Bisection Links**.
   * *Reason*: Localized link over-utilization causes localized Head-of-Line blocking and severe switch arbitration contention at intermediate switching hubs long before the global network capacity is reached.

* **Narrow Link Widths ($\le 32\text{ bits}$)**:
   * **Dominant Component**: **Serialization Latency ($T_{\text{serialization}}$)**.
   * *Reason*: Each packet is chopped into numerous small flits, multiplying per-hop channel holding times, inducing heavy channel occupancy and contention.

---

### Q2: What is the depth of the input buffer and what is the default flow control?

1. **Depth of Input Buffer (in Garnet 3.0 / gem5)**:
   * Defined in `src/mem/ruby/network/garnet/GarnetNetwork.py` and `InputUnit.cc`:
     - **Control Virtual Channels (`buffers_per_ctrl_vc`)**: **`1 Flit`** per VC (for VNet 0 and VNet 1).
     - **Data Virtual Channels (`buffers_per_data_vc`)**: **`4 Flits`** per VC (for VNet 2).
   * Each input port contains `vcs_per_vnet` $\times$ `number_of_virtual_networks` independent FIFO queues. With default settings ($4\text{ VCs/VNet}$, 3 VNets), each router input port possesses $4 \times 1 + 4 \times 1 + 4 \times 4 = \mathbf{24\text{ Flits}}$ total buffer storage capacity.

2. **Default Flow-Control Mechanism**:
   * Garnet employs **Credit-Based Virtual-Channel Flow Control (基于信用的虚通道流控制)** operating at the **Flit granularity (Flit-level)**.
   * **Mechanism**:
     - Upstream routers maintain an exact credit counter (`m_credit_count`) in `OutVcState` for each downstream VC.
     - Whenever a downstream router's `InputUnit` forwards a flit across its crossbar switch to the output link, it frees one buffer slot and immediately sends a **1-cycle Credit message** upstream over a dedicated `CreditLink`.
     - The upstream router increments its credit counter upon receiving the credit. A flit is only allowed to win switch allocation and enter the link if `m_credit_count > 0`, guaranteeing **Zero Buffer Overflow (无丢包 / 无溢出保证)**.
