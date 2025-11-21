#!/usr/bin/env python3
"""
Compare SSF vs LLF Handover Algorithms with Metrics Collection
Run this script to test both algorithms and generate comparison plots
"""

from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from threading import Thread
import time
import math
import matplotlib.pyplot as plt
import sys

class HandoverMetrics:
    """Collect metrics during handover"""
    
    def __init__(self):
        self.timestamps = []
        self.positions = []
        self.rssi_ap1 = []
        self.rssi_ap2 = []
        self.connected_ap = []
        self.handover_events = []
        
    def record(self, timestamp, position, rssi1, rssi2, ap_name):
        """Record a single measurement"""
        self.timestamps.append(timestamp)
        self.positions.append(position)
        self.rssi_ap1.append(rssi1)
        self.rssi_ap2.append(rssi2)
        self.connected_ap.append(ap_name)
    
    def mark_handover(self, timestamp, position, old_ap, new_ap):
        """Mark when handover occurred"""
        self.handover_events.append({
            'time': timestamp,
            'position': position,
            'from': old_ap,
            'to': new_ap
        })
    
    def save_to_csv(self, filename):
        """Save metrics to CSV file"""
        with open(filename, 'w') as f:
            f.write("Timestamp,Position,RSSI_AP1,RSSI_AP2,Connected_AP\n")
            for i in range(len(self.timestamps)):
                f.write(f"{self.timestamps[i]:.2f},{self.positions[i]},"
                       f"{self.rssi_ap1[i]:.1f},{self.rssi_ap2[i]:.1f},"
                       f"{self.connected_ap[i]}\n")
        info(f"*** Metrics saved to {filename}\n")
    
    def get_handover_count(self):
        """Return number of handovers"""
        return len(self.handover_events)
    
    def get_handover_positions(self):
        """Return positions where handovers occurred"""
        return [event['position'] for event in self.handover_events]

class SSFHandover:
    """SSF with metrics collection"""
    
    def __init__(self, net, sta, aps, hysteresis_margin=5):
        self.net = net
        self.sta = sta
        self.aps = aps
        self.hysteresis_margin = hysteresis_margin
        self.current_ap = None
        self.metrics = HandoverMetrics()
        self.start_time = time.time()
        self.ap_positions = {
            aps[0]: ('20', '40', '0'),
            aps[1]: ('100', '40', '0')
        }
    
    def calculate_distance(self, pos1, pos2):
        x1, y1 = float(pos1[0]), float(pos1[1])
        x2, y2 = float(pos2[0]), float(pos2[1])
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def estimate_rssi(self, distance):
        if distance < 1:
            distance = 1
        return -40 - 20 * math.log10(distance)
    
    def select_best_ap(self, current_pos):
        """SSF: Select AP with strongest signal"""
        current_time = time.time() - self.start_time
        
        rssi_values = {}
        for ap in self.aps:
            distance = self.calculate_distance(current_pos, self.ap_positions[ap])
            rssi = self.estimate_rssi(distance)
            rssi_values[ap] = rssi
        
        # Record metrics
        self.metrics.record(
            timestamp=current_time,
            position=float(current_pos[0]),
            rssi1=rssi_values[self.aps[0]],
            rssi2=rssi_values[self.aps[1]],
            ap_name=self.current_ap.name if self.current_ap else 'None'
        )
        
        # SSF logic with hysteresis
        best_ap = max(rssi_values, key=rssi_values.get)
        best_rssi = rssi_values[best_ap]
        current_rssi = rssi_values.get(self.current_ap, float('-inf'))
        
        if self.current_ap and (best_rssi - current_rssi < self.hysteresis_margin):
            return self.current_ap
        
        return best_ap

class LLFHandover:
    """LLF with metrics collection"""
    
    def __init__(self, net, sta, aps):
        self.net = net
        self.sta = sta
        self.aps = aps
        self.current_ap = None
        self.metrics = HandoverMetrics()
        self.start_time = time.time()
        self.ap_loads = {aps[0]: 3, aps[1]: 0}  # Initial load: ap1=3, ap2=0
        self.ap_positions = {
            aps[0]: ('20', '40', '0'),
            aps[1]: ('100', '40', '0')
        }
    
    def calculate_distance(self, pos1, pos2):
        x1, y1 = float(pos1[0]), float(pos1[1])
        x2, y2 = float(pos2[0]), float(pos2[1])
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def estimate_rssi(self, distance):
        if distance < 1:
            distance = 1
        return -40 - 20 * math.log10(distance)
    
    def select_best_ap(self, current_pos):
        """LLF: Select AP with lowest load"""
        current_time = time.time() - self.start_time
        
        rssi_values = {}
        for ap in self.aps:
            distance = self.calculate_distance(current_pos, self.ap_positions[ap])
            rssi = self.estimate_rssi(distance)
            rssi_values[ap] = rssi
        
        # Record metrics
        self.metrics.record(
            timestamp=current_time,
            position=float(current_pos[0]),
            rssi1=rssi_values[self.aps[0]],
            rssi2=rssi_values[self.aps[1]],
            ap_name=self.current_ap.name if self.current_ap else 'None'
        )
        
        # LLF logic: choose least loaded AP (only if signal > -90dBm)
        candidates = [(ap, self.ap_loads[ap]) for ap in self.aps 
                     if rssi_values[ap] >= -90]
        
        if not candidates:
            return self.current_ap
        
        # Sort by load, then by RSSI
        candidates.sort(key=lambda x: (x[1], -rssi_values[x[0]]))
        return candidates[0][0]

def run_test(algorithm_name):
    """Run handover test with specified algorithm"""
    info(f"\n{'='*60}\n")
    info(f"*** Running {algorithm_name} Algorithm Test\n")
    info(f"{'='*60}\n\n")
    
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1', position='10,20,0')
    ap1  = net.addAccessPoint('ap1', ssid='test-ssid', mode='g', channel='1',
                              position='20,40,0', range=60)
    ap2  = net.addAccessPoint('ap2', ssid='test-ssid', mode='g', channel='1',
                              position='100,40,0', range=60)
    c0   = net.addController('c0')

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    
    sta1.setRange(50)

    # Initialize handover controller based on algorithm
    if algorithm_name == "SSF":
        handover_controller = SSFHandover(net, sta1, [ap1, ap2], hysteresis_margin=5)
    else:  # LLF
        handover_controller = LLFHandover(net, sta1, [ap1, ap2])

    info(f"*** Starting mobility with {algorithm_name}\n")
    
    # Move station and collect metrics
    for x in range(10, 121, 5):
        sta1.setPosition(f'{x},20,0')
        
        old_ap = handover_controller.current_ap
        best_ap = handover_controller.select_best_ap((str(x), '20', '0'))
        
        if best_ap != old_ap:
            current_time = time.time() - handover_controller.start_time
            info(f"\n*** HANDOVER at position {x}: {old_ap.name if old_ap else 'None'} -> {best_ap.name}\n")
            
            handover_controller.metrics.mark_handover(
                current_time, x,
                old_ap.name if old_ap else 'None',
                best_ap.name
            )
            
            # Update load for LLF
            if algorithm_name == "LLF":
                if old_ap:
                    handover_controller.ap_loads[old_ap] -= 1
                handover_controller.ap_loads[best_ap] += 1
            
            try:
                if old_ap:
                    sta1.wintfs[0].disconnect(sta1.wintfs[0].associatedTo)
                sta1.wintfs[0].associate(best_ap.wintfs[0])
            except:
                pass
            
            handover_controller.current_ap = best_ap
        
        time.sleep(0.5)  # Shorter delay for faster simulation
    
    info(f"*** {algorithm_name} test complete!\n")
    
    # Save metrics
    handover_controller.metrics.save_to_csv(f'{algorithm_name.lower()}_metrics.csv')
    
    # Clean up
    net.stop()
    
    return handover_controller.metrics

def plot_comparison(ssf_metrics, llf_metrics):
    """Create comparison plots for SSF vs LLF"""
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    fig.suptitle('SSF vs LLF Handover Comparison', fontsize=18, fontweight='bold')
    
    # Plot 1: SSF Signal Strength (only show connected AP highlighted)
    ax1 = fig.add_subplot(gs[0, 0])
    
    # Plot both APs in light color
    ax1.plot(ssf_metrics.positions, ssf_metrics.rssi_ap1, 'b-', 
             label='AP1 RSSI', linewidth=1, alpha=0.3)
    ax1.plot(ssf_metrics.positions, ssf_metrics.rssi_ap2, 'r-', 
             label='AP2 RSSI', linewidth=1, alpha=0.3)
    
    # Highlight the connected AP
    for i in range(len(ssf_metrics.positions)):
        if ssf_metrics.connected_ap[i] == 'ap1':
            ax1.scatter(ssf_metrics.positions[i], ssf_metrics.rssi_ap1[i], 
                       c='blue', s=20, alpha=0.8)
        elif ssf_metrics.connected_ap[i] == 'ap2':
            ax1.scatter(ssf_metrics.positions[i], ssf_metrics.rssi_ap2[i], 
                       c='red', s=20, alpha=0.8)
    
    # Mark handovers with clear vertical lines and labels
    for event in ssf_metrics.handover_events:
        pos = event['position']
        ax1.axvline(x=pos, color='green', linestyle='--', linewidth=3, alpha=0.8)
        ax1.text(pos, -65, f"{event['from']}→{event['to']}", 
                rotation=90, va='bottom', fontsize=9, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    ax1.set_xlabel('Position (m)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('RSSI (dBm)', fontsize=12, fontweight='bold')
    ax1.set_title('SSF: Connected AP Signal (highlighted)', fontsize=13, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.text(70, -85, f'Handovers: {ssf_metrics.get_handover_count()}', 
             fontsize=11, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
    
    # Plot 2: LLF Signal Strength (only show connected AP highlighted)
    ax2 = fig.add_subplot(gs[0, 1])
    
    ax2.plot(llf_metrics.positions, llf_metrics.rssi_ap1, 'b-', 
             label='AP1 RSSI', linewidth=1, alpha=0.3)
    ax2.plot(llf_metrics.positions, llf_metrics.rssi_ap2, 'r-', 
             label='AP2 RSSI', linewidth=1, alpha=0.3)
    
    for i in range(len(llf_metrics.positions)):
        if llf_metrics.connected_ap[i] == 'ap1':
            ax2.scatter(llf_metrics.positions[i], llf_metrics.rssi_ap1[i], 
                       c='blue', s=20, alpha=0.8)
        elif llf_metrics.connected_ap[i] == 'ap2':
            ax2.scatter(llf_metrics.positions[i], llf_metrics.rssi_ap2[i], 
                       c='red', s=20, alpha=0.8)
    
    for event in llf_metrics.handover_events:
        pos = event['position']
        ax2.axvline(x=pos, color='green', linestyle='--', linewidth=3, alpha=0.8)
        ax2.text(pos, -65, f"{event['from']}→{event['to']}", 
                rotation=90, va='bottom', fontsize=9, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    ax2.set_xlabel('Position (m)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('RSSI (dBm)', fontsize=12, fontweight='bold')
    ax2.set_title('LLF: Connected AP Signal (highlighted)', fontsize=13, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.text(70, -85, f'Handovers: {llf_metrics.get_handover_count()}', 
             fontsize=11, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
    
    # Plot 3: Simulated Throughput for SSF
    ax3 = fig.add_subplot(gs[0, 2])
    
    # Simulate throughput based on RSSI (better signal = better throughput)
    ssf_throughput = []
    for i in range(len(ssf_metrics.positions)):
        if ssf_metrics.connected_ap[i] == 'ap1':
            rssi = ssf_metrics.rssi_ap1[i]
        elif ssf_metrics.connected_ap[i] == 'ap2':
            rssi = ssf_metrics.rssi_ap2[i]
        else:
            rssi = -90
        
        # Simulate throughput drop during handover
        is_handover = any(abs(ssf_metrics.positions[i] - event['position']) < 2 
                         for event in ssf_metrics.handover_events)
        
        if is_handover:
            throughput = max(0, 20 + (rssi + 90) * 2) * 0.3  # 70% drop during handover
        else:
            throughput = max(0, 20 + (rssi + 90) * 2)  # Better signal = better throughput
        
        ssf_throughput.append(throughput)
    
    ax3.plot(ssf_metrics.positions, ssf_throughput, 'g-', linewidth=2)
    ax3.fill_between(ssf_metrics.positions, ssf_throughput, alpha=0.3, color='green')
    
    for event in ssf_metrics.handover_events:
        pos = event['position']
        ax3.axvline(x=pos, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax3.annotate('Handover\nDip', xy=(pos, 10), xytext=(pos+10, 5),
                    arrowprops=dict(arrowstyle='->', color='red', lw=2),
                    fontsize=9, fontweight='bold', color='red')
    
    ax3.set_xlabel('Position (m)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Throughput (Mbps)', fontsize=12, fontweight='bold')
    ax3.set_title('SSF: Estimated Throughput', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    avg_throughput = sum(ssf_throughput) / len(ssf_throughput)
    ax3.text(70, max(ssf_throughput)-5, f'Avg: {avg_throughput:.1f} Mbps', 
             fontsize=10, bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    # Plot 4: Simulated Throughput for LLF
    ax4 = fig.add_subplot(gs[1, 0])
    
    llf_throughput = []
    for i in range(len(llf_metrics.positions)):
        if llf_metrics.connected_ap[i] == 'ap1':
            rssi = llf_metrics.rssi_ap1[i]
        elif llf_metrics.connected_ap[i] == 'ap2':
            rssi = llf_metrics.rssi_ap2[i]
        else:
            rssi = -90
        
        is_handover = any(abs(llf_metrics.positions[i] - event['position']) < 2 
                         for event in llf_metrics.handover_events)
        
        if is_handover:
            throughput = max(0, 20 + (rssi + 90) * 2) * 0.3
        else:
            throughput = max(0, 20 + (rssi + 90) * 2)
        
        llf_throughput.append(throughput)
    
    ax4.plot(llf_metrics.positions, llf_throughput, 'purple', linewidth=2)
    ax4.fill_between(llf_metrics.positions, llf_throughput, alpha=0.3, color='purple')
    
    for event in llf_metrics.handover_events:
        pos = event['position']
        ax4.axvline(x=pos, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax4.annotate('Handover\nDip', xy=(pos, 10), xytext=(pos+10, 5),
                    arrowprops=dict(arrowstyle='->', color='red', lw=2),
                    fontsize=9, fontweight='bold', color='red')
    
    ax4.set_xlabel('Position (m)', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Throughput (Mbps)', fontsize=12, fontweight='bold')
    ax4.set_title('LLF: Estimated Throughput', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    avg_throughput = sum(llf_throughput) / len(llf_throughput)
    ax4.text(70, max(llf_throughput)-5, f'Avg: {avg_throughput:.1f} Mbps', 
             fontsize=10, bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    # Plot 5: Throughput Comparison Bar Chart
    ax5 = fig.add_subplot(gs[1, 1])
    
    ssf_avg = sum(ssf_throughput) / len(ssf_throughput)
    llf_avg = sum(llf_throughput) / len(llf_throughput)
    ssf_min = min(ssf_throughput)
    llf_min = min(llf_throughput)
    
    x = ['Average\nThroughput', 'Minimum\nThroughput\n(during handover)']
    ssf_vals = [ssf_avg, ssf_min]
    llf_vals = [llf_avg, llf_min]
    
    x_pos = range(len(x))
    width = 0.35
    
    bars1 = ax5.bar([p - width/2 for p in x_pos], ssf_vals, width, 
                    label='SSF', color='green', alpha=0.7)
    bars2 = ax5.bar([p + width/2 for p in x_pos], llf_vals, width, 
                    label='LLF', color='purple', alpha=0.7)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontweight='bold')
    
    ax5.set_ylabel('Throughput (Mbps)', fontsize=12, fontweight='bold')
    ax5.set_title('Throughput Comparison', fontsize=13, fontweight='bold')
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels(x)
    ax5.legend()
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Plot 6: Handover Position Timeline
    ax6 = fig.add_subplot(gs[1, 2])
    
    ssf_handovers = ssf_metrics.get_handover_positions()
    llf_handovers = llf_metrics.get_handover_positions()
    
    ax6.scatter(ssf_handovers, [1]*len(ssf_handovers), s=300, c='blue', 
               marker='v', label='SSF Handovers', alpha=0.8, edgecolors='black', linewidths=2)
    ax6.scatter(llf_handovers, [2]*len(llf_handovers), s=300, c='red', 
               marker='^', label='LLF Handovers', alpha=0.8, edgecolors='black', linewidths=2)
    
    # Add position labels
    for pos in ssf_handovers:
        ax6.text(pos, 1.15, f'{pos}m', ha='center', fontsize=10, fontweight='bold')
    for pos in llf_handovers:
        ax6.text(pos, 1.85, f'{pos}m', ha='center', fontsize=10, fontweight='bold')
    
    ax6.set_xlabel('Position (m)', fontsize=12, fontweight='bold')
    ax6.set_yticks([1, 2])
    ax6.set_yticklabels(['SSF', 'LLF'], fontsize=12, fontweight='bold')
    ax6.set_title('Handover Positions', fontsize=13, fontweight='bold')
    ax6.legend(loc='upper right')
    ax6.grid(True, alpha=0.3, axis='x')
    ax6.set_ylim(0.5, 2.5)
    ax6.set_xlim(0, 130)
    
    # Plot 7: Summary Statistics (larger box)
    ax7 = fig.add_subplot(gs[2, :])
    ax7.axis('off')
    
    summary_text = f"""
    ╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
    ║                                  COMPARISON SUMMARY                                              ║
    ╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
    
    📊 SSF (Strongest Signal First):                    📊 LLF (Least-Loaded First):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    • Handovers: {ssf_metrics.get_handover_count()}                                   • Handovers: {llf_metrics.get_handover_count()}
    • Positions: {ssf_handovers}                         • Positions: {llf_handovers}
    • Strategy: Signal-based (5dB hysteresis)            • Strategy: Load-based balancing
    • Avg Throughput: {sum(ssf_throughput)/len(ssf_throughput):.1f} Mbps                          • Avg Throughput: {sum(llf_throughput)/len(llf_throughput):.1f} Mbps
    • Min Throughput: {min(ssf_throughput):.1f} Mbps                          • Min Throughput: {min(llf_throughput):.1f} Mbps
    
    🔑 KEY INSIGHTS:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ✓ SSF switches when signal strength improves significantly (maintains better connection quality)
    ✓ LLF switches to distribute load across APs (may accept weaker signal for network balance)
    ✓ Throughput dips occur during handover due to reconnection overhead
    ✓ SSF typically has {"higher" if sum(ssf_throughput) > sum(llf_throughput) else "lower"} average throughput due to {"better signal selection" if sum(ssf_throughput) > sum(llf_throughput) else "load considerations"}
    ✓ Green dashed lines show exact handover positions where AP switch occurred
    """
    
    ax7.text(0.5, 0.5, summary_text, fontsize=10, family='monospace',
            verticalalignment='center', horizontalalignment='center',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8, pad=1))
    
    plt.savefig('ssf_vs_llf_comparison.png', dpi=300, bbox_inches='tight')
    info("*** Comparison plot saved to ssf_vs_llf_comparison.png\n")
    plt.show()

def main():
    """Main function to run both algorithms and compare"""
    info("\n" + "="*60 + "\n")
    info("*** Wi-Fi Handover Algorithm Comparison\n")
    info("*** Testing SSF vs LLF\n")
    info("="*60 + "\n")
    
    # Run SSF test
    ssf_metrics = run_test("SSF")
    time.sleep(2)
    
    # Run LLF test
    llf_metrics = run_test("LLF")
    
    # Generate comparison plots
    info("\n*** Generating comparison plots...\n")
    plot_comparison(ssf_metrics, llf_metrics)
    
    info("\n" + "="*60 + "\n")
    info("*** Analysis Complete!\n")
    info("*** Generated files:\n")
    info("***   - ssf_metrics.csv\n")
    info("***   - llf_metrics.csv\n")
    info("***   - ssf_vs_llf_comparison.png\n")
    info("="*60 + "\n")

if __name__ == '__main__':
    setLogLevel('info')
    main()