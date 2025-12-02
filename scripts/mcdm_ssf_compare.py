#!/usr/bin/env python3
"""
Enhanced SSF vs MCDM comparison with 4 APs and more complex scenario
Shows where MCDM makes significantly different decisions
"""

from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from threading import Thread
import time
import math
import numpy as np

class HandoverComparison:
    """Compare SSF and MCDM decisions with multiple APs"""
    
    def __init__(self, aps, ap_configs):
        """
        Args:
            aps: List of AP objects
            ap_configs: Dict with AP configurations
                       {ap: {'position': (x,y,z), 'load': congestion_factor}}
        """
        self.aps = aps
        self.ap_positions = {}
        self.ap_loads = {}  # Simulated congestion/load per AP
        
        for ap, config in ap_configs.items():
            self.ap_positions[ap] = config['position']
            self.ap_loads[ap] = config.get('load', 1.0)
        
        # Track decisions
        self.ssf_decisions = []
        self.mcdm_decisions = []
        self.positions_analyzed = []
        
        # Hysteresis for SSF
        self.ssf_current_ap = None
        self.ssf_hysteresis = 3  # Reduced for more sensitivity
    
    def calculate_distance(self, pos1, pos2):
        """Calculate Euclidean distance"""
        x1, y1 = float(pos1[0]), float(pos1[1])
        x2, y2 = float(pos2[0]), float(pos2[1])
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def estimate_rssi(self, distance):
        """Path loss model"""
        if distance < 1:
            distance = 1
        return -40 - 20 * math.log10(distance)
    
    def estimate_delay(self, distance, ap):
        """
        Estimate delay with AP-specific congestion.
        Higher load = higher delay (simulates congestion)
        """
        propagation_delay = (distance / 1000) / 300
        processing_delay = 5.0
        
        # Distance-based congestion
        distance_factor = 1 + (distance / 100) * 0.1
        
        # AP-specific load factor (simulates network congestion)
        load_factor = self.ap_loads[ap]
        
        return (propagation_delay + processing_delay) * distance_factor * load_factor
    
    def ssf_decision(self, sta_pos):
        """SSF: Pick strongest RSSI with hysteresis"""
        best_ap = None
        best_rssi = float('-inf')
        current_rssi = None
        
        rssi_values = {}
        
        for ap in self.aps:
            ap_pos = self.ap_positions[ap]
            distance = self.calculate_distance(sta_pos, ap_pos)
            rssi = self.estimate_rssi(distance)
            rssi_values[ap] = rssi
            
            if ap == self.ssf_current_ap:
                current_rssi = rssi
            
            if rssi > best_rssi:
                best_rssi = rssi
                best_ap = ap
        
        # Apply hysteresis
        if self.ssf_current_ap and current_rssi:
            if best_rssi - current_rssi < self.ssf_hysteresis:
                return self.ssf_current_ap, current_rssi, rssi_values
        
        self.ssf_current_ap = best_ap
        return best_ap, best_rssi, rssi_values
    
    def calculate_entropy_weights(self, decision_matrix):
        """Calculate entropy weights"""
        dm = np.abs(decision_matrix)
        
        col_norms = np.sqrt(np.sum(dm ** 2, axis=0))
        col_norms = np.where(col_norms == 0, 1e-10, col_norms)
        normalized = dm / col_norms
        
        m = normalized.shape[0]
        
        if m <= 1:
            return np.array([0.5, 0.5])
        
        entropies = []
        k = 1.0 / np.log(m)
        
        for j in range(normalized.shape[1]):
            column = normalized[:, j]
            col_sum = np.sum(column)
            if col_sum == 0:
                entropies.append(0)
                continue
            
            p = column / col_sum
            p = np.where(p <= 0, 1e-10, p)
            
            entropy = -k * np.sum(p * np.log(p))
            entropies.append(entropy)
        
        entropies = np.array(entropies)
        diversities = 1 - entropies
        
        total = np.sum(diversities)
        if total == 0 or np.isnan(total):
            return np.array([0.5, 0.5])
        
        weights = diversities / total
        
        if np.any(np.isnan(weights)):
            return np.array([0.5, 0.5])
        
        return weights
    
    def apply_topsis(self, decision_matrix, weights):
        """Apply TOPSIS"""
        col_norms = np.sqrt(np.sum(decision_matrix ** 2, axis=0))
        col_norms = np.where(col_norms == 0, 1e-10, col_norms)
        normalized = decision_matrix / col_norms
        
        weighted = normalized * weights
        
        ideal = np.array([np.max(weighted[:, 0]), np.min(weighted[:, 1])])
        negative = np.array([np.min(weighted[:, 0]), np.max(weighted[:, 1])])
        
        dist_ideal = np.sqrt(np.sum((weighted - ideal) ** 2, axis=1))
        dist_negative = np.sqrt(np.sum((weighted - negative) ** 2, axis=1))
        
        scores = dist_negative / (dist_ideal + dist_negative + 1e-10)
        
        if np.any(np.isnan(scores)):
            scores = np.ones(len(scores)) / len(scores)
        
        best_idx = np.argmax(scores)
        
        return best_idx, scores
    
    def mcdm_decision(self, sta_pos):
        """MCDM: Entropy + TOPSIS"""
        candidates = []
        
        for ap in self.aps:
            ap_pos = self.ap_positions[ap]
            distance = self.calculate_distance(sta_pos, ap_pos)
            rssi = self.estimate_rssi(distance)
            delay = self.estimate_delay(distance, ap)  # Now considers AP load
            candidates.append([rssi, delay])
        
        decision_matrix = np.array(candidates)
        weights = self.calculate_entropy_weights(decision_matrix)
        best_idx, scores = self.apply_topsis(decision_matrix, weights)
        
        return self.aps[best_idx], candidates[best_idx][0], weights, scores, decision_matrix
    
    def analyze_position(self, sta_pos_tuple):
        """Analyze and compare both algorithms at current position"""
        x, y = sta_pos_tuple
        sta_pos = (str(x), str(y), '0')
        
        ssf_ap, ssf_rssi, ssf_rssi_values = self.ssf_decision(sta_pos)
        mcdm_ap, mcdm_rssi, weights, scores, decision_matrix = self.mcdm_decision(sta_pos)
        
        self.ssf_decisions.append(ssf_ap.name)
        self.mcdm_decisions.append(mcdm_ap.name)
        self.positions_analyzed.append((x, y))
        
        metrics = {}
        for i, ap in enumerate(self.aps):
            ap_pos = self.ap_positions[ap]
            distance = self.calculate_distance(sta_pos, ap_pos)
            rssi = self.estimate_rssi(distance)
            delay = self.estimate_delay(distance, ap)
            metrics[ap.name] = {
                'distance': distance,
                'rssi': rssi,
                'delay': delay,
                'topsis_score': scores[i],
                'load_factor': self.ap_loads[ap]
            }
        
        return {
            'position': (x, y),
            'ssf_choice': ssf_ap.name,
            'mcdm_choice': mcdm_ap.name,
            'agree': ssf_ap == mcdm_ap,
            'weights': {'rssi': weights[0], 'delay': weights[1]},
            'metrics': metrics
        }

def move_and_compare(net, sta, comparator):
    """Move station through complex path"""
    time.sleep(3)
    
    info("\n" + "="*90 + "\n")
    info("*** ENHANCED COMPARISON: 4 APs with varying congestion levels\n")
    info("*** AP1: Low congestion  | AP2: High congestion\n")
    info("*** AP3: Medium congestion | AP4: Low congestion\n")
    info("="*90 + "\n\n")
    
    # More complex path through all APs
    path = [
        # Start near AP1
        (15, 25), (25, 25), (35, 25),
        # Move toward center (between AP1 and AP3)
        (45, 35), (50, 45),
        # Move toward AP3
        (55, 55), (60, 65),
        # Move toward AP2 (high congestion)
        (70, 60), (80, 50), (90, 40),
        # Near AP2
        (100, 35), (105, 30),
        # Move down toward AP4
        (105, 20), (100, 10),
        # Near AP4
        (90, 10), (80, 10), (70, 10)
    ]
    
    for x, y in path:
        sta.setPosition(f'{x},{y},0')
        
        result = comparator.analyze_position((x, y))
        
        info(f"\n{'='*90}\n")
        info(f"POSITION: ({x}, {y})\n")
        info(f"{'='*90}\n")
        
        # Show metrics with load factor
        info("\nNetwork Metrics (Load: 1.0=normal, >1.0=congested):\n")
        info(f"{'AP':<10} {'Dist':<10} {'RSSI':<12} {'Delay':<12} {'Load':<10} {'TOPSIS':<10}\n")
        info(f"{'-'*80}\n")
        for ap_name, m in result['metrics'].items():
            info(f"{ap_name:<10} {m['distance']:>6.1f}m   "
                 f"{m['rssi']:>8.1f}dBm  {m['delay']:>8.2f}ms   "
                 f"{m['load_factor']:>6.1f}x    {m['topsis_score']:>8.3f}\n")
        
        # Show MCDM weights
        info(f"\nMCDM Analysis:\n")
        info(f"  Weights → RSSI: {result['weights']['rssi']:.3f}, Delay: {result['weights']['delay']:.3f}\n")
        
        if result['weights']['delay'] > 0.5:
            info(f"  (Delay is dominant - more variation across APs)\n")
        else:
            info(f"  (RSSI is dominant - more variation across APs)\n")
        
        # Show decisions with explanation
        info(f"\nAlgorithm Decisions:\n")
        ssf_metrics = result['metrics'][result['ssf_choice']]
        mcdm_metrics = result['metrics'][result['mcdm_choice']]
        
        info(f"  SSF  → {result['ssf_choice']:<4} "
             f"(RSSI: {ssf_metrics['rssi']:>6.1f}dBm, ignores delay)\n")
        info(f"  MCDM → {result['mcdm_choice']:<4} "
             f"(RSSI: {mcdm_metrics['rssi']:>6.1f}dBm, Delay: {mcdm_metrics['delay']:>5.1f}ms)\n")
        
        if result['agree']:
            info(f"  ✓ AGREEMENT\n")
        else:
            info(f"  ✗ DISAGREEMENT!\n")
            info(f"  → SSF picked {result['ssf_choice']} (stronger signal)\n")
            info(f"  → MCDM picked {result['mcdm_choice']} (better overall: considers delay/congestion)\n")
            
            # Explain why MCDM is better
            if mcdm_metrics['delay'] < ssf_metrics['delay']:
                delay_improvement = ssf_metrics['delay'] - mcdm_metrics['delay']
                info(f"  → MCDM choice has {delay_improvement:.1f}ms LOWER delay!\n")
        
        time.sleep(1.2)
    
    # Enhanced summary
    info(f"\n{'='*90}\n")
    info("*** FINAL COMPARISON SUMMARY\n")
    info(f"{'='*90}\n")
    
    total = len(comparator.positions_analyzed)
    agreements = sum(1 for i in range(total) 
                    if comparator.ssf_decisions[i] == comparator.mcdm_decisions[i])
    disagreements = total - agreements
    
    ssf_handovers = sum(1 for i in range(1, total) 
                       if comparator.ssf_decisions[i] != comparator.ssf_decisions[i-1])
    mcdm_handovers = sum(1 for i in range(1, total) 
                        if comparator.mcdm_decisions[i] != comparator.mcdm_decisions[i-1])
    
    info(f"\nPositions analyzed: {total}\n")
    info(f"Agreements: {agreements} ({agreements/total*100:.0f}%)\n")
    info(f"Disagreements: {disagreements} ({disagreements/total*100:.0f}%)\n")
    info(f"\nHandover Statistics:\n")
    info(f"  SSF handovers:  {ssf_handovers}\n")
    info(f"  MCDM handovers: {mcdm_handovers}\n")
    
    if mcdm_handovers < ssf_handovers:
        info(f"  → MCDM performed {ssf_handovers - mcdm_handovers} FEWER handovers (more stable)\n")
    elif mcdm_handovers > ssf_handovers:
        info(f"  → MCDM performed {mcdm_handovers - ssf_handovers} MORE handovers (more responsive to quality)\n")
    
    info(f"\nDecision Timeline:\n")
    info(f"Position    SSF   MCDM  Agree\n")
    info(f"{'-'*35}\n")
    for i, pos in enumerate(comparator.positions_analyzed):
        agree_mark = "✓" if comparator.ssf_decisions[i] == comparator.mcdm_decisions[i] else "✗"
        info(f"({pos[0]:3d},{pos[1]:2d})    {comparator.ssf_decisions[i]}   "
             f"{comparator.mcdm_decisions[i]}    {agree_mark}\n")
    
    info(f"\n{'='*90}\n")
    info("*** KEY INSIGHTS:\n")
    info("*** 1. SSF only sees signal strength - picks closest/strongest AP\n")
    info("*** 2. MCDM sees the full picture - balances signal AND delay/congestion\n")
    info("*** 3. When APs have different congestion levels, MCDM avoids overloaded APs\n")
    info("*** 4. Result: Better user experience with lower latency connections\n")
    info(f"{'='*90}\n")
    
    info("\n*** Movement and comparison complete!\n")

def run_comparison():
    """Run enhanced comparison with 4 APs"""
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes with 4 APs\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1', position='15,25,0')
    
    # 4 APs in a grid pattern
    ap1 = net.addAccessPoint('ap1', ssid='network', mode='g', channel='1',
                             position='30,50,0', range=50)
    ap2 = net.addAccessPoint('ap2', ssid='network', mode='g', channel='6',
                             position='100,50,0', range=50)
    ap3 = net.addAccessPoint('ap3', ssid='network', mode='g', channel='11',
                             position='60,70,0', range=50)
    ap4 = net.addAccessPoint('ap4', ssid='network', mode='g', channel='1',
                             position='90,10,0', range=50)
    
    c0 = net.addController('c0')

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()
    net.plotGraph(max_x=140, max_y=90)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    ap3.start([c0])
    ap4.start([c0])
    
    sta1.setRange(50)

    # Configure APs with different congestion levels
    ap_configs = {
        ap1: {'position': ('30', '50', '0'), 'load': 1.0},    # Low congestion
        ap2: {'position': ('100', '50', '0'), 'load': 2.5},   # HIGH congestion (busy AP)
        ap3: {'position': ('60', '70', '0'), 'load': 1.5},    # Medium congestion
        ap4: {'position': ('90', '10', '0'), 'load': 1.0}     # Low congestion
    }
    
    comparator = HandoverComparison([ap1, ap2, ap3, ap4], ap_configs)
    
    info("*** Starting complex mobility pattern\n")
    info("*** AP2 is heavily congested (load factor: 2.5x)\n")
    info("*** Watch how MCDM avoids it while SSF doesn't!\n")
    
    mobility_thread = Thread(target=move_and_compare, args=(net, sta1, comparator))
    mobility_thread.daemon = True
    mobility_thread.start()
    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_comparison()