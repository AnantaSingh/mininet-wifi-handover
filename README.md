# WiFi Handover: SSF vs LLF vs MCDM

 Analysis of Strongest Signal First (SSF), Least-Loaded First (LLF), and Multi-Criteria Decision Making (MCDM) handover algorithms using Mininet-WiFi.

## Quick Start
```bash
# Install Mininet-WiFi
git clone https://github.com/intrig-unicamp/mininet-wifi
cd mininet-wifi
sudo util/install.sh -Wlnfv

# Clone and run
git clone https://github.com/AnantaSingh/mininet-wifi-handover
cd wifi-handover-project
sudo mn -c

# Run individual algorithms
sudo python3 scripts/ssf2.py
sudo python3 scripts/llf_handover_dynamic.py
sudo python3 scripts/mcdm_ssf_compare.py
```

## Main Scripts

- **`scripts/ssf2.py`** - Strongest Signal First (SSF) algorithm implementation with RSSI-based handover and hysteresis
- **`scripts/llf_handover_dynamic.py`** - Least-Loaded First (LLF) algorithm with dynamic load balancing
- **`scripts/mcdm_ssf_compare.py`** - Multi-Criteria Decision Making (MCDM) vs SSF comparison with enhanced scenarios

## Algorithms

**SSF (Strongest Signal First):** Selects AP with strongest RSSI signal with hysteresis margin to prevent ping-ponging. Higher throughput, optimized for signal quality.

**LLF (Least-Loaded First):** Selects AP with least number of connected stations. Better load balancing across APs, optimized for network capacity.

**MCDM (Multi-Criteria Decision Making):** Uses multiple criteria with weighted scoring to make handover decisions. More sophisticated decision-making process.

## Network Setup

### SSF (`ssf2.py`)
- **2 APs**: AP1 at (20,40), AP2 at (100,40), 60m range each
- **Station**: Starts at (10,20), moves x=10 → 120m in 5m steps
- **Station range**: 50m
- **Hysteresis**: 5dB margin to prevent ping-ponging

### LLF (`llf_handover_dynamic.py`)
- **2 APs**: AP1 at (20,40), AP2 at (100,40), 60m range each
- **Stations**: 
  - sta1 (mobile): Starts at (10,20), moves x=10 → 120m in 5m steps
  - sta2 & sta3 (static): Initially connected to AP1 to create load imbalance
- **Station range**: 50m
- **Load tracking**: Dynamically updates AP load after each handover

### MCDM (`mcdm_ssf_compare.py`)
- **4 APs**: 
  - AP1: (30,50), range=50m, load=1.0x (low congestion)
  - AP2: (100,50), range=50m, load=2.5x (high congestion)
  - AP3: (60,70), range=50m, load=1.5x (medium congestion)
  - AP4: (90,10), range=50m, load=1.0x (low congestion)
- **Station**: Starts at (15,25), follows complex path through all APs
- **Station range**: 50m
- **Comparison**: SSF vs MCDM decision-making at each position

## Troubleshooting
```bash
sudo mn -c              # Clean Mininet
sudo killall hostapd    # Kill processes
```

## Requirements

Ubuntu 20.04+, Python 3.8+, matplotlib, sudo access

## References

Fontes et al. (2015), Kassar et al. (2008), IEEE 802.11

---

**Authors:** Ananta Singh, Siddhi Patil | Nov 2025
