#!/usr/bin/env python3
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from threading import Thread
import time
import math
import random


class SSFHandover:
    """
    Strongest Signal First (SSF) - RSSI-based handover with:
      - path-loss + random shadowing
      - hysteresis margin
      - handover delay logging
    """

    def __init__(self, net, sta, aps, hysteresis_margin=5, shadow_sigma=2.0):
        self.net = net
        self.sta = sta
        self.aps = aps
        self.hysteresis_margin = hysteresis_margin  # dB
        self.shadow_sigma = shadow_sigma            # dB std-dev for shadowing
        self.current_ap = None

        # For logging handover events
        self.handover_events = []

        # Store AP positions at initialization (fallbacks included)
        self.ap_positions = {}
        for ap in aps:
            try:
                self.ap_positions[ap] = ap.params['position']
            except (KeyError, AttributeError):
                if hasattr(ap, 'position'):
                    self.ap_positions[ap] = ap.position
                else:
                    # Default positions based on AP name (3-AP triangular layout)
                    if 'ap1' in ap.name:
                        self.ap_positions[ap] = ('20', '40', '0')
                    elif 'ap2' in ap.name:
                        self.ap_positions[ap] = ('100', '40', '0')
                    elif 'ap3' in ap.name:
                        self.ap_positions[ap] = ('60', '10', '0')
                    else:
                        self.ap_positions[ap] = ('50', '50', '0')

    def get_position(self, node):
        """Get position of a node (station or AP)."""
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
        """Calculate 2D Euclidean distance between two (x,y,*) positions."""
        x1, y1 = float(pos1[0]), float(pos1[1])
        x2, y2 = float(pos2[0]), float(pos2[1])
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def estimate_rssi(self, distance):
        """
        Estimate RSSI using log-distance path-loss with optional random shadowing.
        RSSI(d) = -40 - 20 log10(d) + N(0, shadow_sigma^2)
        """
        if distance < 1:
            distance = 1
        rssi = -40 - 20 * math.log10(distance)
        if self.shadow_sigma > 0:
            rssi += random.gauss(0, self.shadow_sigma)
        return rssi

    def select_best_ap(self):
        """Select AP with strongest signal (with hysteresis decision)."""
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
        if self.current_ap and current_ap_rssi is not None:
            if best_rssi - current_ap_rssi < self.hysteresis_margin:
                info(
                    f"\n*** SSF Analysis: Staying with {self.current_ap.name} "
                    f"(RSSI={current_ap_rssi:.1f}dBm, best={best_rssi:.1f}dBm, "
                    f"margin={best_rssi - current_ap_rssi:.1f}dB < {self.hysteresis_margin}dB)\n"
                )
                return self.current_ap

        # Display all RSSI values at this position
        info(f"\n*** SSF Analysis at position {current_pos}:\n")
        for ap, rssi in rssi_values.items():
            marker = " <-- STRONGEST" if ap == best_ap else ""
            info(f"*** {ap.name}: RSSI={rssi:.1f}dBm{marker}\n")

        return best_ap

    def log_handover(self, old_ap, new_ap, position, t_start, t_end):
        """Store handover event for later analysis."""
        delay = t_end - t_start
        event = {
            "from": old_ap.name if old_ap else "None",
            "to": new_ap.name,
            "position": position,
            "t_start": t_start,
            "t_end": t_end,
            "delay": delay,
        }
        self.handover_events.append(event)
        info(
            f"*** Handover delay: {delay * 1000:.1f} ms at position {position}, "
            f"{event['from']} -> {event['to']}\n"
        )


def move_station_ssf(net, sta, handover_controller):
    """Move station with SSF handover, logging events."""
    time.sleep(3)
    info("*** Starting SSF (Strongest Signal First) handover movement\n")

    # Move STA from x=10 to x=120 in 5m steps
    for x in range(10, 121, 5):
        sta.setPosition(f'{x},20,0')
        current_pos = handover_controller.get_position(sta)

        best_ap = handover_controller.select_best_ap()

        if best_ap != handover_controller.current_ap:
            old_ap = handover_controller.current_ap
            info(
                f"\n*** SSF HANDOVER! "
                f"{old_ap.name if old_ap else 'None'} -> {best_ap.name}\n"
            )
            info(f"*** Reason: {best_ap.name} has strongest signal\n")

            t_start = time.time()
            try:
                if old_ap:
                    sta.wintfs[0].disconnect(sta.wintfs[0].associatedTo)
                sta.wintfs[0].associate(best_ap.wintfs[0])
            except Exception as e:
                info(f"*** Association note: {e}\n")
            t_end = time.time()

            handover_controller.current_ap = best_ap
            handover_controller.log_handover(old_ap, best_ap, current_pos, t_start, t_end)

        time.sleep(1)

    info("*** Movement complete!\n")
    if handover_controller.handover_events:
        info("*** Handover Summary:\n")
        for ev in handover_controller.handover_events:
            info(
                f"*** At position {ev['position']}: "
                f"{ev['from']} -> {ev['to']} in {ev['delay'] * 1000:.1f} ms\n"
            )
    else:
        info("*** No handovers recorded.\n")


def start_background_traffic(sta, server_ip, duration=60, label="sta1"):
    """
    Start an iperf client from a station to the server in the background.
    Used to measure throughput during movement.
    """
    info(f"*** Starting iperf traffic from {label} to server {server_ip}\n")
    # '-t duration' seconds, '-i 1' report interval, log to file
    sta.cmd(f'iperf -c {server_ip} -t {duration} -i 1 > {label}_iperf.log &')


def start_load_spike(sta2, sta3, server_ip, start_after=15, duration=20):
    """
    Start extra iperf flows from sta2 and sta3 after some delay.
    This simulates a 'load spike' on AP2.
    """
    time.sleep(start_after)
    info("*** Starting load spike on AP2 (sta2 + sta3 iperf clients)\n")
    sta2.cmd(f'iperf -c {server_ip} -t {duration} -i 1 > sta2_iperf.log &')
    sta3.cmd(f'iperf -c {server_ip} -t {duration} -i 1 > sta3_iperf.log &')


def run():
    net = Mininet_wifi(controller=Controller)

    info("*** Creating nodes\n")
    # One mobile station (STA1)
    sta1 = net.addStation('sta1', ip='10.0.0.1/24', position='10,20,0')

    # Extra stations near AP2 for load spikes
    sta2 = net.addStation('sta2', ip='10.0.0.2/24', position='95,40,0')
    sta3 = net.addStation('sta3', ip='10.0.0.3/24', position='100,45,0')

    # 3 APs in a triangular-ish layout, same SSID/channel (single logical network)
    ap1 = net.addAccessPoint(
        'ap1', ssid='ssf-ssid', mode='g', channel='1',
        position='20,40,0', range=60
    )
    ap2 = net.addAccessPoint(
        'ap2', ssid='ssf-ssid', mode='g', channel='1',
        position='100,40,0', range=60
    )
    ap3 = net.addAccessPoint(
        'ap3', ssid='ssf-ssid', mode='g', channel='1',
        position='60,10,0', range=60
    )

    # Wired host to act as iperf server
    h1 = net.addHost('h1', ip='10.0.0.100/24')

    c0 = net.addController('c0')

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()

    # Connect wired host to AP1 (AP1 acts as an OVS switch + AP)
    net.addLink(h1, ap1)

    net.plotGraph(max_x=140, max_y=90)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    ap3.start([c0])

    # Set ranges (optional, already somewhat controlled by 'range' on APs)
    sta1.setRange(50)
    sta2.setRange(50)
    sta3.setRange(50)

    # Start iperf server on h1
    info("*** Starting iperf server on h1\n")
    # TCP server, 1s stats, logs to file
    h1.cmd('iperf -s -i 1 > iperf_server.log &')

    # Initialize SSF handover controller with shadowing noise
    info("*** Initializing SSF handover controller (hysteresis=5dB, shadow_sigma=2dB)\n")
    handover_controller = SSFHandover(
        net, sta1, [ap1, ap2, ap3],
        hysteresis_margin=5,
        shadow_sigma=2.0
    )

    # Start throughput measurement from STA1 to h1
    start_background_traffic(sta1, h1.IP(), duration=60, label="sta1")

    # Start load spike thread (to stress AP2 via sta2 & sta3)
    spike_thread = Thread(
        target=start_load_spike,
        args=(sta2, sta3, h1.IP(), 15, 25)
    )
    spike_thread.daemon = True
    spike_thread.start()

    # Start mobility + SSF handover in background
    info("*** Starting mobility with SSF\n")
    mobility_thread = Thread(
        target=move_station_ssf,
        args=(net, sta1, handover_controller)
    )
    mobility_thread.daemon = True
    mobility_thread.start()

    info("*** Algorithm: SSF (Strongest Signal First) with 5dB hysteresis, 3 APs, noise, iperf, load spike\n")

    # Interactive CLI (you can inspect: sta1 iw dev sta1-wlan0 link, etc.)
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
