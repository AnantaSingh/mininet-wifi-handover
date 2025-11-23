#!/usr/bin/env python3
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
import matplotlib.pyplot as plt
import time
import math

class LLFHandover:
    """Least-Loaded First (LLF) - Pure load balancing, prioritizes least busy AP"""
    
    def __init__(self, net, sta, aps, min_rssi_threshold=-90):
        self.net = net
        self.sta = sta
        self.aps = aps
        self.min_rssi_threshold = min_rssi_threshold
        self.current_ap = None
        self.ap_loads = {ap: 0 for ap in aps}  # Track number of stations per AP
        
        # Store AP positions at initialization
        self.ap_positions = {}
        for ap in aps:
            try:
                self.ap_positions[ap] = ap.params['position']
            except (KeyError, AttributeError):
                if hasattr(ap, 'position'):
                    self.ap_positions[ap] = ap.position
                else:
                    if 'ap1' in ap.name:
                        self.ap_positions[ap] = ('20', '40', '0')
                    else:
                        self.ap_positions[ap] = ('100', '40', '0')
    
    def get_position(self, node):
        """Get position of a node"""
        if node in self.ap_positions:
            return self.ap_positions[node]
        try:
            return node.params['position']
        except (KeyError, AttributeError):
            try:
                return node.position
            except AttributeError:
                return ('10', '20', '0')
        
    def calculate_distance(self, pos1, pos2):
        """Calculate Euclidean distance"""
        x1, y1 = float(pos1[0]), float(pos1[1])
        x2, y2 = float(pos2[0]), float(pos2[1])
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def estimate_rssi(self, distance):
        """Estimate RSSI using path loss model"""
        if distance < 1:
            distance = 1
        return -40 - 20 * math.log10(distance)
    
    def get_ap_load(self, ap):
        """Get current load on AP (number of associated stations)"""
        # Return tracked load (dynamically updated)
        return self.ap_loads.get(ap, 0)
    
    def select_best_ap(self):
        """Select AP with LEAST LOAD (prioritize load over signal strength)"""
        # Get current position
        try:
            current_pos = self.sta.params['position']
        except (KeyError, AttributeError):
            try:
                current_pos = self.sta.position
            except AttributeError:
                current_pos = ('10', '20', '0')
        
        candidate_aps = []
        
        info(f"\n*** LLF Analysis at position {current_pos}:\n")
        info(f"*** Strategy: Choose LEAST LOADED AP (load is priority, not signal)\n")
        
        # Display current load state
        info(f"*** Current AP loads: ")
        for ap in self.aps:
            info(f"{ap.name}={self.ap_loads[ap]} ")
        info("\n")
        
        # Find APs that are reachable (minimal signal threshold)
        for ap in self.aps:
            try:
                ap_pos = ap.params['position']
            except (KeyError, AttributeError):
                ap_pos = ap.position
            
            distance = self.calculate_distance(current_pos, ap_pos)
            rssi = self.estimate_rssi(distance)
            load = self.get_ap_load(ap)
            
            info(f"*** {ap.name}: Load={load} stations, RSSI={rssi:.1f}dBm")
            
            if rssi >= self.min_rssi_threshold:
                candidate_aps.append((ap, rssi, load))
                info(f" ✓ Reachable\n")
            else:
                info(f" ✗ Out of range\n")
        
        if not candidate_aps:
            info("*** No APs reachable! Staying with current.\n")
            return self.current_ap
        
        # Sort by load (ascending), use RSSI as tiebreaker
        candidate_aps.sort(key=lambda x: (x[2], -x[1]))
        
        best_ap = candidate_aps[0][0]
        best_load = candidate_aps[0][2]
        best_rssi = candidate_aps[0][1]
        
        # Show decision reasoning
        if len(candidate_aps) > 1:
            second_ap = candidate_aps[1][0]
            second_load = candidate_aps[1][2]
            second_rssi = candidate_aps[1][1]
            info(f"*** Choosing {best_ap.name} (Load={best_load}) over {second_ap.name} (Load={second_load})\n")
            if second_rssi > best_rssi:
                info(f"*** NOTE: {second_ap.name} has better signal ({second_rssi:.1f}dBm vs {best_rssi:.1f}dBm) "
                     f"but {best_ap.name} is less loaded!\n")
        else:
            info(f"*** Selected: {best_ap.name} (Load={best_load}, RSSI={best_rssi:.1f}dBm)\n")
        
        return best_ap


class MobilitySimulationLLF:
    """Mobility simulation with LLF handover using matplotlib timers"""
    
    def __init__(self, net, sta, handover_controller):
        self.net = net
        self.sta = sta
        self.handover_controller = handover_controller
        self.x_positions = list(range(10, 121, 5))
        self.current_index = 0
        self.timer = None
        self.started = False
        
    def start(self):
        """Start the mobility simulation"""
        if not self.started:
            self.started = True
            info("*** Starting LLF (Least-Loaded First) handover\n")
            # Schedule first update after 3 seconds
            self.timer = plt.gcf().canvas.new_timer(interval=3000)
            self.timer.add_callback(self.begin_movement)
            self.timer.single_shot = True
            self.timer.start()
    
    def begin_movement(self):
        """Begin the actual movement"""
        info("*** Movement initiated!\n")
        # Now schedule regular updates every 1 second
        self.timer = plt.gcf().canvas.new_timer(interval=1000)
        self.timer.add_callback(self.update_position)
        self.timer.start()
        self.update_position()
    
    def update_position(self):
        """Update station position with LLF handover - called from matplotlib timer"""
        if self.current_index >= len(self.x_positions):
            info("*** Movement complete!\n")
            if self.timer:
                self.timer.stop()
            return
        
        x = self.x_positions[self.current_index]
        self.current_index += 1
        
        # Update position (this will trigger graph update in main thread)
        self.sta.setPosition(f'{x},20,0')
        
        # Perform LLF handover decision
        best_ap = self.handover_controller.select_best_ap()
        
        if best_ap and best_ap != self.handover_controller.current_ap:
            old_ap = self.handover_controller.current_ap
            
            info(f"\n*** LLF HANDOVER! {old_ap.name if old_ap else 'None'} -> {best_ap.name}\n")
            info(f"*** Reason: {best_ap.name} has lower load\n")
            
            # ✅ DYNAMIC LOAD UPDATE - THIS IS THE FIX!
            if old_ap:
                self.handover_controller.ap_loads[old_ap] = max(0, self.handover_controller.ap_loads[old_ap] - 1)
                info(f"*** Updated {old_ap.name} load: {self.handover_controller.ap_loads[old_ap]+1} -> {self.handover_controller.ap_loads[old_ap]}\n")
            
            self.handover_controller.ap_loads[best_ap] = self.handover_controller.ap_loads[best_ap] + 1
            info(f"*** Updated {best_ap.name} load: {self.handover_controller.ap_loads[best_ap]-1} -> {self.handover_controller.ap_loads[best_ap]}\n")
            
            try:
                if old_ap:
                    self.sta.wintfs[0].disconnect()
                self.sta.wintfs[0].associate(best_ap.wintfs[0])
            except Exception as e:
                info(f"*** Association error: {e}\n")
            
            self.handover_controller.current_ap = best_ap


def run():
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1', position='10,20,0')
    sta2 = net.addStation('sta2', ip='10.0.0.2', position='15,45,0')  # Additional station for load
    sta3 = net.addStation('sta3', ip='10.0.0.3', position='25,35,0')  # Additional station
    
    ap1  = net.addAccessPoint('ap1', ssid='llf-ssid', mode='g', channel='1',
                              position='20,40,0', range=60)
    ap2  = net.addAccessPoint('ap2', ssid='llf-ssid', mode='g', channel='1',
                              position='100,40,0', range=60)
    c0   = net.addController('c0')

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()
    
    net.plotGraph(max_x=140, max_y=90)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    
    for sta in net.stations:
        sta.setRange(50)

    info("*** Initializing LLF handover controller (min_rssi=-90dBm)\n")
    info("*** LLF DYNAMICALLY tracks load - updates after each handover\n")
    handover_controller = LLFHandover(net, sta1, [ap1, ap2], min_rssi_threshold=-90)
    
    # Simulate initial load by associating other stations to ap1
    info("*** Creating initial load scenario:\n")
    info("*** - sta2 and sta3 will connect to ap1\n")
    info("*** - ap1 initial load = 2 stations\n")
    info("*** - ap2 initial load = 0 stations\n")
    try:
        sta2.wintfs[0].associate(ap1.wintfs[0])
        sta3.wintfs[0].associate(ap1.wintfs[0])
        handover_controller.ap_loads[ap1] = 2  # Set initial load
    except Exception as e:
        info(f"*** Warning: Could not associate sta2/sta3: {e}\n")
        handover_controller.ap_loads[ap1] = 2  # Set load anyway for simulation

    info("*** Setting up mobility simulation\n")
    mobility = MobilitySimulationLLF(net, sta1, handover_controller)
    mobility.start()

    info("*** Algorithm: LLF (Least-Loaded First) with DYNAMIC load tracking\n")
    info("*** Watch the graph window - sta1 will start moving in 3 seconds!\n")
    info("*** Load counters will update in real-time after handovers\n")
    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()