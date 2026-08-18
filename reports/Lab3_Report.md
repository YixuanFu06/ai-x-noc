# Lab 3 Report: Topology & Flow Control

**Course:** Network-on-Chip (NoC) / Computer Architecture  
**Author:** Yixuan Fu  
**Date:** August 2026  
**Environment:** gem5 v23.0.0.1 (Garnet 3.0 Standalone, Ubuntu 20.04 on WSL)

---

## 1. Task 1: 16-Node Ring (1D-Torus) Topology & Custom Routing Algorithm

### 1.1 Topology Implementation (`Ring.py`)
We implemented a 16-node bidirectional Ring topology in `ai-x-noc/src_modified/configs/topologies/Ring.py` (symlinked to `gem5/configs/topologies/Ring.py`):
* **Nodes & Routers:** 16 Routers (`Router 0` to `Router 15`) and 16 Network Interfaces (NIs).
* **External Links (`ExtLink`):** Connect each NI to its local router (`Local` port).
* **Internal Bidirectional Links (`IntLink`):**
  - **Clockwise (East) Link:** Connects Router $i \to (i + 1) \pmod{16}$ with `src_outport="East"` and `dst_inport="West"`.
  - **Counter-Clockwise (West) Link:** Connects Router $i \to (i - 1 + 16) \pmod{16}$ with `src_outport="West"` and `dst_inport="East"`.

---

### 1.2 Custom Shortest-Path Ring Routing Algorithm (`RoutingUnit.cc`)
In `ai-x-noc/src_modified/src/mem/ruby/network/garnet/RoutingUnit.cc`, we implemented the custom routing logic in `RoutingUnit::outportComputeCustom()`:

```cpp
int
RoutingUnit::outportComputeCustom(RouteInfo route,
                                  int inport,
                                  PortDirection inport_dirn)
{
    PortDirection outport_dirn = "Unknown";
    int num_routers = m_router->get_net_ptr()->getNumRouters();
    int my_id = m_router->get_id();
    int dest_id = route.dest_router;

    assert(my_id != dest_id);

    // Calculate clockwise and counter-clockwise hop distance
    int dist_cw = (dest_id - my_id + num_routers) % num_routers;
    int dist_ccw = (my_id - dest_id + num_routers) % num_routers;

    // Route along the shortest path on the bidirectional ring
    if (dist_cw <= dist_ccw) {
        outport_dirn = "East";
    } else {
        outport_dirn = "West";
    }

    return m_outports_dirn2idx[outport_dirn];
}
```

---

### 1.3 Experimental Setup & Quantitative Results

We executed comprehensive sweeps across 5 traffic patterns (`uniform_random`, `neighbor`, `tornado`, `transpose`, `shuffle`) at injection rates $0.01 \sim 0.50$ for 10,000 cycles ($10^7$ Ticks). Additionally, we ran a 16-node 4×4 Mesh baseline (`Mesh_XY`) for comparison.

All extracted data is stored in `ai-x-noc/data/lab3_task1/summary_lab3_task1.csv`.

#### Quantitative Summary (16-Node Ring vs. 4×4 Mesh)

| Topology & Traffic Pattern | Zero-load Latency (Cycles) | Measured Avg Hops | Theoretical Avg Hops | Saturation Injection Rate |
| :--- | :---: | :---: | :---: | :---: |
| **`Ring (uniform_random)`** | **6.47** | **4.00** | $\frac{1}{16}\sum \min(k, 16-k) = \mathbf{4.00}$ | **~ 0.45** |
| **`Mesh_XY 4x4 (uniform_random)`** | **4.97** | **2.50** | $\mathbf{2.50}$ | **> 0.50** |
| **`Ring (neighbor)`** | **3.99** | **1.50** | $\mathbf{1.50}$ | **> 0.50** |
| **`Mesh_XY 4x4 (neighbor)`** | **3.99** | **1.50** | $\mathbf{1.50}$ | **> 0.50** |
| **`Ring (shuffle)`** | **6.04** | **3.50** | $\mathbf{3.50}$ | **~ 0.45** |
| **`Ring (transpose)`** | **5.96** | **3.48** | $\mathbf{3.48}$ | **> 0.50** |

---

### 1.4 Visualizations

Generated plots in `ai-x-noc/reports/figures/`:
* **Ring Topology Latency-Throughput across Patterns**: `figures/lab3_task1_ring_latency_throughput.png`
* **16-Node Ring vs. 4×4 Mesh Comparison**: `figures/lab3_task1_ring_vs_mesh_comparison.png`

---

### 1.5 Architectural Performance Analysis

1. **Hop Count & Zero-Load Latency Comparison (Ring vs. Mesh):**
   * In a 16-node system, the **1D Ring** has a network diameter of $D = N/2 = 8$ hops and an average distance of $4.00$ hops.
   * In contrast, the **4×4 2D Mesh** has a network diameter of $D = (4-1) + (4-1) = 6$ hops and an average distance of $2.50$ hops.
   * Consequently, under `uniform_random` traffic, the zero-load latency of the Ring ($6.47\text{ Cycles}$) is approximately **$1.5\text{ Cycles}$ higher** than that of the 4×4 Mesh ($4.97\text{ Cycles}$), matching the $1.5$ hop difference precisely ($\Delta \text{Latency} = \Delta \text{Hops} \times (t_{\text{router}} + t_{\text{link}}) = 1.5 \times 1 = 1.5\text{ Cycles}$).

2. **Bisection Bandwidth & Saturation Comparison:**
   * A 1D bidirectional ring has a bisection width of $2 \times 2 = 4$ links (2 in each direction).
   * A 4×4 2D mesh has a bisection width of $4 \times 2 = 8$ links.
   * The higher bisection bandwidth of the 2D Mesh allows it to sustain higher throughput without saturation under heavy uniform traffic, whereas the Ring's narrower bisection bandwidth leads to earlier congestion onset under high loads ($\sim 0.45$).

---

## 2. Task 2: Wormhole Flow-Control Implementation & Buffer Dimension Trade-off

### 2.1 Microarchitecture & Code Implementation
We implemented wormhole flow control with deep buffer support via the `--wormhole` flag:
1. **Buffer Depth & Credit Initialization (`GarnetNetwork.cc` & `OutVcState.cc`):**
   When `--wormhole` is passed, `m_buffers_per_ctrl_vc` is configured to **16**, providing 16 buffer slots per virtual channel.
2. **Deep Buffer Ingestion (`InputUnit.cc`):**
   In `InputUnit::wakeup()`, when `--wormhole` is enabled, subsequent single-flit packets (`HEAD_TAIL_`) entering an already active VC are permitted to buffer into the VC's FIFO queue rather than triggering an idle-state assertion.
3. **Credit & VC State Management (`OutputUnit.cc` & `SwitchAllocator.cc`):**
   * In `OutputUnit::has_free_vc()` and `select_free_vc()`, downstream availability is governed by `outVcState[vc].has_credit()` ($> 0$), allowing up to 16 packets to be pipelined consecutively.
   * In `SwitchAllocator::arbitrate_outports()`, after forwarding a single-flit packet, if additional packets remain in the input VC queue, the next flit's output port is computed immediately via `m_router->route_compute()`, returning an incremental credit to the upstream router while **retaining VC active state (`free_signal = false`)**. Only when the input queue is completely drained is `free_signal = true` signaled.

---

### 2.2 Experimental Evaluation (3 Buffer Configurations)

We performed 90 simulation runs across 15 injection rates ($0.01 \sim 0.50$) on a 16-node 4×4 Mesh under `uniform_random` and `tornado` traffic patterns.

All raw and summary metrics are recorded in `ai-x-noc/data/lab3_task2/summary_lab3_task2.csv`.

#### Quantitative Summary (Uniform Random Traffic, 16-Node 4×4 Mesh)

| Microarchitectural Configuration | Virtual Channels (VCs) | Depth Per VC | Total Slots / Port | Zero-Load Latency | Saturation Ingestion Rate | Max Sustained Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Config 1: `VC = 1, Depth = 1`** | **1** | **1** | 1 Flit | **5.01 Cycles** | **~ 0.20** | **~ 0.259 pkts/node/cycle** |
| **Config 2: `VC = 16, Depth = 1`** | **16** | **1** | 16 Flits | **4.97 Cycles** | **> 0.50** | **~ 0.497 pkts/node/cycle** |
| **Config 3: `VC = 1, Depth = 16 (Wormhole)`** | **1** | **16** | 16 Flits | **4.98 Cycles** | **~ 0.35 - 0.40** | **~ 0.398 pkts/node/cycle** |

---

### 2.3 Visualizations

Generated plots in `ai-x-noc/reports/figures/`:
* **Combined Buffer Dimension Trade-off**: `figures/lab3_task2_combined_buffer_analysis.png`
* **Uniform Random Comparison**: `figures/lab3_task2_comparison_uniform_random.png`
* **Tornado Comparison**: `figures/lab3_task2_comparison_tornado.png`

---

### 2.4 In-Depth Comparative Analysis

#### 1. `VC = 1, Depth = 1` vs. `VC = 1, Depth = 16 (Wormhole)` (Impact of Buffer Depth)
* **Performance Gain:** Increasing buffer depth from 1 to 16 within a single VC raises the network saturation threshold dramatically from **$0.20$ to $0.40$**, boosting peak throughput by **$+53.7\%$** ($0.259 \to 0.398\text{ pkts/node/cycle}$).
* **Mechanism:** With only 1 buffer slot, a transient pipeline stall at a downstream router immediately blocks upstream links, causing rapid congestion propagation and buffer starvation across the network. Deep buffering absorbs burstiness and decouples upstream injection from transient downstream stalls.

#### 2. `VC = 16, Depth = 1` vs. `VC = 1, Depth = 16 (Wormhole)` (VC Dimension vs. Depth Dimension Trade-off)
Under an identical total buffering budget of **16 flits per port**:
* **Throughput & Head-of-Line (HoL) Blocking:**
  * `VC = 16, Depth = 1` achieves higher sustained throughput ($> 0.50$) than `VC = 1, Depth = 16` ($~ 0.40$).
  * **Cause:** In `VC = 1, Depth = 16`, packets are queued sequentially in a single FIFO. If the head-of-line packet is blocked waiting for a congested outport, all following packets in the FIFO—even those destined for idle output ports—are blocked (**Intra-VC Head-of-Line Blocking**).
  * In `VC = 16, Depth = 1`, 16 independent virtual channels allow packets destined for non-congested ports to bypass blocked packets completely (**Inter-VC HoL Elimination**).
* **Hardware Complexity & Silicon Area Trade-off:**
  * `VC = 1, Depth = 16 (Wormhole)` requires only a **1-bit VC allocator**, simple 1-way arbitration, and standard FIFO circular pointers.
  * `VC = 16, Depth = 1` requires a **16-way VC allocator**, multi-stage arbiters, and extensive multiplexing logic, consuming substantially more silicon area and dynamic switching energy.
  * **Architectural Insight:** Wormhole flow control (`VC = 1, Depth = 16`) offers a highly area-efficient compromise, delivering ~80% of multi-VC throughput at a fraction of the control logic complexity.
