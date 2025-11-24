#!/usr/bin/env python3
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
import matplotlib.pyplot as plt
import time

class MobilitySimulation:
    def __init__(self, net, sta):
        self.net = net
        self.sta = sta
        self.current_ap = None
        self.x_positions = list(range(10, 121, 5))
        self.current_index = 0
        self.timer = None
        self.started = False
        
    def start(self):
        """Start the mobility simulation"""
        if not self.started:
            self.started = True
            info("*** Starting station movement\n")
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
        """Update station position - called from matplotlib timer"""
        if self.current_index >= len(self.x_positions):
            info("*** Movement complete!\n")
            if self.timer:
                self.timer.stop()
            return
        
        x = self.x_positions[self.current_index]
        self.current_index += 1
        
        # Update position (this will trigger graph update in main thread)
        self.sta.setPosition(f'{x},20,0')
        
        # Check which AP the station is associated with
        try:
            connected_ap = None
            if hasattr(self.sta, 'wintfs') and len(self.sta.wintfs) > 0:
                intf = self.sta.wintfs[0]
                if hasattr(intf, 'associatedTo') and intf.associatedTo:
                    connected_ap = intf.associatedTo.name
            
            # Detect handover
            if connected_ap != self.current_ap and connected_ap is not None:
                info(f"\n*** HANDOVER! sta1: {self.current_ap or 'None'} -> {connected_ap} at position ({x},20,0)\n")
                self.current_ap = connected_ap
            
            # Get signal strength
            rssi_info = ""
            if connected_ap:
                rssi = self.sta.wintfs[0].rssi if hasattr(self.sta.wintfs[0], 'rssi') else 'N/A'
                rssi_info = f" | RSSI: {rssi} dBm"
            
            info(f"*** Position: ({x},20,0) | AP: {connected_ap or 'None'}{rssi_info}\n")
        except Exception as e:
            info(f"*** Position: ({x},20,0) | Error: {e}\n")

def run():
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', ip='10.0.0.1', position='10,20,0')
    ap1  = net.addAccessPoint('ap1', ssid='handover-ssid', mode='g', channel='1',
                              position='20,40,0', range=60)
    ap2  = net.addAccessPoint('ap2', ssid='handover-ssid', mode='g', channel='1',
                              position='100,40,0', range=60)
    c0   = net.addController('c0')

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()
    
    # Enable the plot
    net.plotGraph(max_x=140, max_y=90)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    
    # Enable station to roam between APs
    info("*** Enabling roaming\n")
    sta1.setRange(50)

    # Create mobility simulation using matplotlib timer (thread-safe)
    info("*** Setting up mobility simulation\n")
    mobility = MobilitySimulation(net, sta1)
    mobility.start()

    info("*** Watch the graph window - sta1 will start moving in 3 seconds!\n")
    info("*** You should see handover between ap1 and ap2\n")
    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
