# Lab 1 Report: Running Synthetic Traffic in Garnet

**Course:** AI+X Computing Acceleration
**Date:** August 2026  
**Environment:** gem5 v23.0.0.1 (Garnet 3.0 Standalone, Ubuntu 20.04 on WSL)

---

## 1. Task 1: Running Synthetic Traffic & Clock Frequency Analysis

### 1.1 Baseline Simulation (1GHz Default)
Using Garnet Standalone mode, we ran a synthetic traffic simulation with an 8×8 Mesh topology (64 nodes), uniform random traffic pattern, simulation length of 10,000 cycles, and an injection rate of 0.01 packets/node/cycle:

```bash
./build/NULL/gem5.opt \
  configs/example/garnet_synth_traffic.py \
  --network=garnet --num-cpus=64 --num-dirs=64 \
  --topology=Mesh_XY --mesh-rows=8 \
  --inj-vnet=0 --synthetic=uniform_random \
  --sim-cycles=10000 --injectionrate=0.01
```

Extracting metrics from `m5out/stats.txt` yielded:
* `packets_injected::total` = 5
* `packets_received::total` = 2
* `average_packet_queueing_latency` = 1000 (Tick)
* `average_packet_network_latency` = 3000 (Tick)
* `average_packet_latency` = 4000 (Tick)
* `average_hops` = 1.500000 (Count)

### 1.2 Comparison: Changing Clock Frequency to 2GHz
We reran the test command with `--sys-clock=2GHz`:

```bash
./build/NULL/gem5.opt \
  configs/example/garnet_synth_traffic.py \
  --network=garnet --num-cpus=64 --num-dirs=64 \
  --topology=Mesh_XY --mesh-rows=8 \
  --inj-vnet=0 --synthetic=uniform_random \
  --sim-cycles=10000 --injectionrate=0.01 \
  --sys-clock=2GHz
```

### 1.3 Results Comparison & Analysis

| Metric | 1 GHz Default (`--sys-clock=1GHz`) | 2 GHz (`--sys-clock=2GHz`) | Analysis |
| :--- | :--- | :--- | :--- |
| **Global Frequency** | $10^{12}$ Ticks/s (1 ps/Tick) | $10^{12}$ Ticks/s (1 ps/Tick) | Set by `m5.ticks.setGlobalFrequency("1ps")` |
| **Clock Period** | 1000 Ticks (1 ns) | 500 Ticks (0.5 ns) | Halved clock period at 2GHz |
| **Simulated Duration** | 10000 Ticks (10 ns) | 10000 Ticks (10 ns) | Exit condition matches `curTick() >= simCycles` |
| **Simulated Cycles** | $10000 / 1000 = \mathbf{10\text{ Cycles}}$ | $10000 / 500 = \mathbf{20\text{ Cycles}}$ | At 2GHz, twice as many cycles elapsed |
| **Packets Injected** | 5 | 13 | Proportionally doubled ($64 \times 0.01 \times 20 = 12.8$) |
| **Packets Received** | 2 | 7 | Proportionally increased with more cycles |
| **Queueing Latency** | 1000 Ticks (1 Cycle) | 500 Ticks (1 Cycle) | 1-cycle queueing latency equals 500 ps at 2GHz |
| **Average Latency** | 4000 Ticks (4 Cycles) | 2928.57 Ticks (~5.8 Cycles) | Measured in Ticks; absolute time is lower |

**Key Findings:**
1. `GlobalFrequency` in gem5 represents the resolution of simulator events (1 Tick = 1 ps).
2. `sys-clock` defines the clock period of the hardware blocks. At 2GHz, 1 Cycle = 500 Ticks.
3. Because `GarnetSyntheticTraffic.cc` checks `curTick() >= simCycles` at line 175, the simulation exits when simulated ticks reach 10,000. Doubling the clock frequency doubles the number of elapsed cycles (from 10 to 20 cycles) in the same simulated time window (10 ns), leading to twice as many injected packets and halving the tick duration of 1-cycle queue delays.

---

## 2. Task 2: Units Completion and Reception Rate Metric

### 2.1 Completing Units in `GarnetNetwork.cc`
In `src/mem/ruby/network/garnet/GarnetNetwork.cc`, statistics were registered without unit designations, causing gem5 to print `(Unspecified)` for all network metrics in `stats.txt`.

We updated `GarnetNetwork::regStats()` by binding every statistic to its standard `statistics::units`:
- **Packet/Flit Counts & Hops**: Added `.unit(statistics::units::Count::get())`
  - `m_packets_received`, `m_packets_injected`, `m_flits_received`, `m_flits_injected`, `m_avg_hops`, `data_packets`, `ctrl_packets`.
- **Latencies**: Added `.unit(statistics::units::Tick::get())`
  - `m_packet_network_latency`, `m_packet_queueing_latency`, `m_avg_packet_latency`, `m_avg_packet_network_latency`, `m_avg_packet_queueing_latency`, `m_avg_packet_vnet_latency`, `m_avg_packet_vqueue_latency`, and their flit counterparts.
- **Ratios & Load**: Added `.unit(statistics::units::Ratio::get())`
  - `m_average_link_utilization`, `m_average_vc_load`.

### 2.2 Adding Reception Rate Metric
We created an automated extraction script (`scripts/extract_network_stats.sh`) that parses `m5out/stats.txt` and computes **Reception Rate**:
$$\text{Reception Rate (packets/node/cycle)} = \frac{\text{total\_packets\_received}}{\text{num\_cpus} \times \text{sim\_cycles}}$$

For our baseline run:
$$\text{Reception Rate} = \frac{2}{64 \times 10000} \approx 0.00000313 \text{ packets/node/cycle}$$

### 2.3 Verified Output of `network_stats.txt`
```text
packets_injected = 5                       (Count)
packets_received = 2                       (Count)
average_packet_queueing_latency = 1000     (Tick)
average_packet_network_latency = 3000      (Tick)
average_packet_latency = 4000              (Tick)
average_hops = 1.500000                    (Count)
reception_rate = 0.00000313 (packets/node/cycle)
```

---

## 3. Task 3: Questions & Detailed Answers

### Q1: Input Parameter Options & Default Parameter Locations
* **What input parameter options are available for `garnet_synth_traffic.py`?**
  1. **Traffic Generator Options:**
     - `--synthetic`: Traffic pattern (`uniform_random`, `tornado`, `bit_complement`, `bit_reverse`, `bit_rotation`, `neighbor`, `shuffle`, `transpose`).
     - `-i`, `--injectionrate`: Packet injection rate per node per cycle (float between 0.0 and 1.0).
     - `--precision`: Number of decimal digits for injection rate (default: 3).
     - `--sim-cycles`: Total simulation cycles (default: 1000).
     - `--num-packets-max`: Max packets to inject before stopping (-1 for unlimited).
     - `--single-sender-id` / `--single-dest-id`: Restrict traffic injection to specific source/destination node.
     - `--inj-vnet`: Virtual network to inject into (0 or 1 for 1-flit control packets, 2 for 5-flit data packets, -1 for all).
  2. **Network & Topology Options:**
     - `--network`: Network model (`garnet` or `simple`).
     - `--topology`: Network topology (e.g., `Mesh_XY`, `Mesh_dir_x`, `Pt2Pt`, etc.).
     - `--mesh-rows`: Number of rows in 2D mesh topology.
     - `--num-cpus` / `--num-dirs`: Number of traffic injectors/CPUs and directory destinations.
     - `--vcs-per-vnet`: Number of Virtual Channels (VCs) per Virtual Network (default: 4).
     - `--router-latency`: Router pipeline latency in cycles (default: 1).
     - `--link-latency`: Link traversal latency in cycles (default: 1).
     - `--link-width-bits`: Physical link bandwidth in bits (default: 128).
     - `--routing-algorithm`: Routing logic (`0`: Table-based, `1`: XY routing, `2`: Custom).
  3. **System & Clock Options:**
     - `--sys-clock`: Clock frequency of system components (default: `1GHz`).
     - `--ruby-clock`: Clock frequency of Ruby interconnect subsystems.
     - `--sys-voltage`: Supply voltage for voltage domain.

* **Where are the default parameters defined?**
  - Traffic and injector options: `configs/example/garnet_synth_traffic.py` and `src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.py`.
  - Topology & Network options: `configs/network/Network.py` and `src/mem/ruby/network/garnet/GarnetNetwork.py`.
  - General system/Ruby options: `configs/common/Options.py` and `configs/ruby/Ruby.py`.

---

### Q2: Units of Simulation Metrics & Tick-Cycle Relationship
* **What is the unit of `sim-cycles`?**
  - **Conceptually:** It represents clock cycles (Count of cycles).
  - **In gem5 Implementation:** In `GarnetSyntheticTraffic.cc` (line 175), the termination condition is evaluated as `if (curTick() >= simCycles)`. Thus, in the standalone tester, the numerical value is checked directly against **Ticks** (picoseconds by default).
* **What is the unit of `router-latency` and `link-latency`?**
  - Both are in **Cycles** (clock cycles of the router / network clock domain).
* **What is the relationship between Tick and Cycle?**
  - A **Tick** is gem5's fundamental, fixed global discrete time resolution (default: 1 Tick = 1 ps, or $10^{12}$ Ticks/sec).
  - A **Cycle** is the duration of one period of a component's clock domain.
  - Mathematical relationship:
    $$\text{Clock Period (in Ticks)} = \frac{\text{GlobalFrequency}}{\text{ClockFrequency}}$$
    For example:
    - At 1 GHz: $1\text{ Cycle} = \frac{10^{12}}{10^9} = 1000\text{ Ticks} = 1\text{ ns}$.
    - At 2 GHz: $1\text{ Cycle} = \frac{10^{12}}{2 \times 10^9} = 500\text{ Ticks} = 0.5\text{ ns}$.

---

### Q3: Unit of `injectionrate`
* **What is the unit of `injectionrate`?**
  - **`packets / node / cycle`** (packets generated per node per clock cycle).
  - Each node evaluates a pseudo-random number $r \in [0, 1)$ at each clock cycle. If $r < \text{injectionrate}$, a packet is generated and enqueued.

---

### Q4: Definitions of `GarnetNetworkInterface` and `GarnetRouter`
* **Where are `GarnetNetworkInterface` and `GarnetRouter` defined?**
  1. **`GarnetNetworkInterface` (NetworkInterface):**
     - C++ Header: `src/mem/ruby/network/garnet/NetworkInterface.hh`
     - C++ Implementation: `src/mem/ruby/network/garnet/NetworkInterface.cc`
     - Python SimObject: `src/mem/ruby/network/garnet/GarnetNetwork.py` (`class GarnetNetworkInterface(ClockedObject)`)
  2. **`GarnetRouter` (Router):**
     - C++ Header: `src/mem/ruby/network/garnet/Router.hh`
     - C++ Implementation: `src/mem/ruby/network/garnet/Router.cc`
     - Python SimObject: `src/mem/ruby/network/garnet/GarnetNetwork.py` (`class GarnetRouter(BasicRouter)`)

---

### Q5: Packet Flow Across Garnet Modules
* **1. In which module(s) are packets generated and injected into the network?**
  - **Packet Generation:** Generated by `GarnetSyntheticTraffic` (`src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.cc` in `generatePkt()`).
  - **Packet Injection:** Converted from messages into flits (head, body, tail) and injected into the network by `NetworkInterface` (`src/mem/ruby/network/garnet/NetworkInterface.cc` in `flitisizeAndSend()` and `scheduleFlit()`).
* **2. In which module(s) are packets buffered during transmission?**
  - **Input Buffers:** Buffered in the virtual channels of `InputUnit` inside routers (`src/mem/ruby/network/garnet/InputUnit.cc` and `VirtualChannel.cc`).
  - **NI Queues:** Buffered in NI protocol buffers and output FIFO queues (`NetworkInterface::m_ni_buffers`).
  - **Output Buffers:** Buffered temporarily in `OutputUnit` (`src/mem/ruby/network/garnet/OutputUnit.cc`).
* **3. In which module(s) does the program determine if packets can be sent downstream?**
  - **Switch Allocation & Credit Check:** `SwitchAllocator` (`src/mem/ruby/network/garnet/SwitchAllocator.cc`). It performs arbitration and checks downstream buffer availability using the credit counter via `m_outvc_state[outport][outvc].has_credits()`.
  - **Crossbar Traversal:** `CrossbarSwitch` (`src/mem/ruby/network/garnet/CrossbarSwitch.cc`) moves the flit from the input unit to the output unit once switch allocation succeeds.
  - **Credit Return:** `CreditLink` / `Credit` conveys credits back to the upstream router to increment available buffer credits in `OutVcState`.
