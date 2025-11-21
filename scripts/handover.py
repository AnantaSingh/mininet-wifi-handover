#!/usr/bin/env python3
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from threading import Thread
import time

def move_station(net, sta):
    """Move station in a separate thread"""
    time.sleep(3)  # Wait for network to be ready
    info("*** Starting station movement\n")
    
    current_ap = None
    
    # Move station from x=10 to x=120
    for x in range(10, 121, 5):
        sta.setPosition(f'{x},20,0')
        
        # Check which AP the station is associated with
        try:
            connected_ap = None
            if hasattr(sta, 'wintfs') and len(sta.wintfs) > 0:
                intf = sta.wintfs[0]
                if hasattr(intf, 'associatedTo') and intf.associatedTo:
                    connected_ap = intf.associatedTo.name
            
            # Detect handover
            if connected_ap != current_ap and connected_ap is not None:
                info(f"\n*** HANDOVER! sta1: {current_ap or 'None'} -> {connected_ap} at position ({x},20,0)\n")
                current_ap = connected_ap
            
            # Get signal strength
            rssi_info = ""
            if connected_ap:
                rssi = sta.wintfs[0].rssi if hasattr(sta.wintfs[0], 'rssi') else 'N/A'
                rssi_info = f" | RSSI: {rssi} dBm"
            
            info(f"*** Position: ({x},20,0) | AP: {connected_ap or 'None'}{rssi_info}\n")
        except Exception as e:
            info(f"*** Position: ({x},20,0) | Error: {e}\n")
        
        time.sleep(1)
    
    info("*** Movement complete!\n")

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
    
    net.plotGraph(max_x=140, max_y=90)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    
    # Enable station to roam between APs
    info("*** Enabling roaming\n")
    sta1.setRange(50)

    info("*** Starting mobility thread\n")
    mobility_thread = Thread(target=move_station, args=(net, sta1))
    mobility_thread.daemon = True
    mobility_thread.start()

    info("*** Watch the graph window - sta1 will start moving in 3 seconds!\n")
    info("*** You should see handover between ap1 and ap2\n")
    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()