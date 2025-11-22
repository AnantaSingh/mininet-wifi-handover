# WiFi Handover: SSF vs LLF

Comparative analysis of Strongest Signal First (SSF) and Least-Loaded First (LLF) handover algorithms using Mininet-WiFi.

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
sudo python3 comparison_fixed.py
```

**Output:** `ssf_metrics.csv`, `llf_metrics.csv`, `ssf_vs_llf_comparison.png`

## Files

- `comparison_fixed.py` - Main script, runs both algorithms
- `ssf_handover_fixed.py` - SSF with GUI
- `llf_handover_fixed.py` - LLF with GUI
- `handover_fixed.py` - Basic demo

## Algorithms

**SSF:** Selects strongest signal (5dB hysteresis). Higher throughput (45-50 Mbps), 1-2 handovers at 60-70m.

**LLF:** Selects least-loaded AP. Better load balance (38-42 Mbps), 1 handover at 50-60m.

## Network Setup

- 2 APs at (20,40) and (100,40), 60m range
- Station moves 10m → 120m in 5m steps
- Log-distance propagation (exponent=3)

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
