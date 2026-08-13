# ai-x-noc: AI & X Lab

This repository contains the lab assignments and final project for the AI & X course, based on the **gem5 simulator** and its **Garnet** on-chip network model.

The goal of this project is to study, implement, and analyze key aspects of NoC design, including network topologies, routing algorithms, and flow control mechanisms.

## Repository Structure

```text
ai-x-noc/
├── reports/          # Lab reports (PDFs) and final presentation slides
├── scripts/          # Automation scripts for running simulations and plotting data
├── src_modified/     # Modified/added gem5 files (matching the gem5 directory structure)
│   ├── configs/
│   │   └── topologies/
│   └── src/
│       └── mem/
│           └── ruby/
│               └── network/
│                   └── garnet/
└── LICENSE           # Multi-license file (MIT for original code, BSD 3-Clause for gem5 code)
```

---

## Getting Started

To compile and run simulations, you need to set up the official `gem5` repository alongside this repository.

### 1. Prerequisites & gem5 Setup

First, install the required dependencies (on Ubuntu):
```bash
sudo apt install build-essential git m4 scons zlib1g zlib1g-dev \
    libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
    python3-dev libboost-all-dev pkg-config
```

Clone the `gem5` repository at the required version `v23.0.0.1` into a directory next to `ai-x-noc`:
```bash
git clone https://github.com/gem5/gem5.git
cd gem5
git checkout v23.0.0.1
pip install -r requirements.txt
```

### 2. Linking Modified Source Files

This repository uses a **symbolic link (soft link)** workflow to keep our custom modifications separate from the main gem5 codebase while allowing compiler builds to pick up changes automatically.

Use the following commands to link files from `ai-x-noc/src_modified` to `gem5` (run from the root directory of your workspace where both `ai-x-noc` and `gem5` are located):

#### On Linux / macOS:
```bash
# Example: Link a custom topology file (once created)
ln -sf $(pwd)/ai-x-noc/src_modified/configs/topologies/Ring.py $(pwd)/gem5/configs/topologies/Ring.py

# Example: Link a modified C++ source file (once created)
ln -sf $(pwd)/ai-x-noc/src_modified/src/mem/ruby/network/garnet/GarnetNetwork.cc $(pwd)/gem5/src/mem/ruby/network/garnet/GarnetNetwork.cc
ln -sf $(pwd)/ai-x-noc/src_modified/src/mem/ruby/network/garnet/GarnetNetwork.hh $(pwd)/gem5/src/mem/ruby/network/garnet/GarnetNetwork.hh
```

#### On Windows (PowerShell):
```powershell
# Example: Link a custom topology file (once created)
New-Item -ItemType SymbolicLink -Path ".\gem5\configs\topologies\Ring.py" -Target "..\..\ai-x-noc\src_modified\configs\topologies\Ring.py"
```

### 3. Building gem5 (Garnet Standalone)

Go to the `gem5` directory and compile with the standalone network protocol:
```bash
cd gem5
scons build/NULL/gem5.opt PROTOCOL=Garnet_standalone -j$(nproc)
```

### 4. Running Simulations

Run synthetic traffic simulations using the following example command:
```bash
./build/NULL/gem5.opt \
  configs/example/garnet_synth_traffic.py \
  --network=garnet \
  --num-cpus=64 \
  --num-dirs=64 \
  --topology=Mesh_XY \
  --mesh-rows=8 \
  --inj-vnet=0 \
  --synthetic=uniform_random \
  --sim-cycles=10000 \
  --injectionrate=0.01
```

Simulation stats will be outputted to `gem5/m5out/stats.txt`.
