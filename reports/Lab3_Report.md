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
