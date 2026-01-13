#!/usr/bin/env python3
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
import matplotlib.pyplot as plt
import time
import math

class SSFHandover:
    """Strongest Signal First (SSF) - Pure RSSI-based handover with hysteresis"""
    
    def __init__(self, net, sta, aps, hysteresis_margin=5):
        self.net = net
        self.sta = sta
        self.aps = aps
        self.hysteresis_margin = hysteresis_margin  # dB
        self.current_ap = None
        
        # Store AP positions at initialization
        self.ap_positions = {}
        for ap in aps:
            try:
                self.ap_positions[ap] = ap.params['position']
            except (KeyError, AttributeError):
                # Fallback - get from position attribute
                if hasattr(ap, 'position'):
                    self.ap_positions[ap] = ap.position
                else:
                    # Default positions based on AP name
                    if 'ap1' in ap.name:
                        self.ap_positions[ap] = ('20', '40', '0')
                    else:
                        self.ap_positions[ap] = ('100', '40', '0')
        
    def get_position(self, node):
        """Get position of a node (station or AP)"""
        if node in self.ap_positions:
            return self.ap_positions[node]
        
        # For station, get current position
        try:
            return node.params['position']
        except (KeyError, AttributeError):
            try:
                return node.position
            except AttributeError:
                return ('10', '20', '0')  # Default
    
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
    
    def select_best_ap(self):
        """Select AP with strongest signal (with hysteresis)"""
        current_pos = self.get_position(self.sta)
        
        best_ap = None
        best_rssi = float('-inf')
        current_ap_rssi = None
        
        rssi_values = {}
        
        # Calculate RSSI for all APs
        for ap in self.aps:
            ap_pos = self.get_position(ap)
            distance = self.calculate_distance(current_pos, ap_pos)
            rssi = self.estimate_rssi(distance)
            rssi_values[ap] = rssi
            
            if ap == self.current_ap:
                current_ap_rssi = rssi
            
            if rssi > best_rssi:
                best_rssi = rssi
                best_ap = ap
        
        # Apply hysteresis: only switch if new AP is significantly better
        if self.current_ap and current_ap_rssi:
            if best_rssi - current_ap_rssi < self.hysteresis_margin:
                # Stay with current AP (not enough improvement)
                info(f"\n*** SSF Analysis: Staying with {self.current_ap.name} "
                     f"(RSSI={current_ap_rssi:.1f}dBm, best={best_rssi:.1f}dBm, "
                     f"margin={best_rssi-current_ap_rssi:.1f}dB < {self.hysteresis_margin}dB)\n")
                return self.current_ap
        
        # Display all RSSI values
        info(f"\n*** SSF Analysis at position {current_pos}:\n")
        for ap, rssi in rssi_values.items():
            marker = " <-- STRONGEST" if ap == best_ap else ""
            info(f"*** {ap.name}: RSSI={rssi:.1f}dBm{marker}\n")
        
        return best_ap


class MobilitySimulationSSF:
    """Mobility simulation with SSF handover using matplotlib timers"""
    
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
            info("*** Starting SSF (Strongest Signal First) handover\n")
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
        """Update station position with SSF handover - called from matplotlib timer"""
        if self.current_index >= len(self.x_positions):
            info("*** Movement complete!\n")
            if self.timer:
                self.timer.stop()
            return
        
        x = self.x_positions[self.current_index]
        self.current_index += 1
        
        # Update position (this will trigger graph update in main thread)
        self.sta.setPosition(f'{x},20,0')
        
        # Perform SSF handover decision
        best_ap = self.handover_controller.select_best_ap()
        
        if best_ap != self.handover_controller.current_ap:
            info(f"\n*** SSF HANDOVER! {self.handover_controller.current_ap.name if self.handover_controller.current_ap else 'None'} -> {best_ap.name}\n")
            info(f"*** Reason: {best_ap.name} has strongest signal\n")
            
            try:
                if self.handover_controller.current_ap:
                    self.sta.wintfs[0].disconnect(self.sta.wintfs[0].associatedTo)
                self.sta.wintfs[0].associate(best_ap.wintfs[0])
            except Exception as e:
                info(f"*** Association note: {e}\n")
            
            self.handover_controller.current_ap = best_ap


def run():
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1', position='10,20,0')
    ap1  = net.addAccessPoint('ap1', ssid='ssf-ssid', mode='g', channel='1',
                              position='20,40,0', range=60)
    ap2  = net.addAccessPoint('ap2', ssid='ssf-ssid', mode='g', channel='1',
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
    
    sta1.setRange(50)

    info("*** Initializing SSF handover controller (hysteresis=5dB)\n")
    handover_controller = SSFHandover(net, sta1, [ap1, ap2], hysteresis_margin=5)

    info("*** Setting up mobility simulation\n")
    mobility = MobilitySimulationSSF(net, sta1, handover_controller)
    mobility.start()

    info("*** Algorithm: SSF (Strongest Signal First) with 5dB hysteresis\n")
    info("*** Watch the graph window - sta1 will start moving in 3 seconds!\n")
    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
