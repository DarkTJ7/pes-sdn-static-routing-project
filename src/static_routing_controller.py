from collections import defaultdict

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import arp, ethernet, ether_types, ipv4, packet
from ryu.ofproto import ofproto_v1_3


class StaticRoutingController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    ROUTE_COOKIE = 0x1
    ROUTE_PRIORITY = 100

    HOSTS = {
        "10.0.0.1": {"name": "h1", "mac": "00:00:00:00:00:01"},
        "10.0.0.2": {"name": "h2", "mac": "00:00:00:00:00:02"},
        "10.0.0.3": {"name": "h3", "mac": "00:00:00:00:00:03"},
        "10.0.0.4": {"name": "h4", "mac": "00:00:00:00:00:04"},
    }

    # Fixed static paths. The alternate path s1-s3-s4 is intentionally unused.
    ROUTES = {
        ("10.0.0.1", "10.0.0.4"): [
            {"dpid": 1, "in_port": 1, "out_port": 2},
            {"dpid": 2, "in_port": 2, "out_port": 3},
            {"dpid": 4, "in_port": 2, "out_port": 1},
        ],
        ("10.0.0.4", "10.0.0.1"): [
            {"dpid": 4, "in_port": 1, "out_port": 2},
            {"dpid": 2, "in_port": 3, "out_port": 2},
            {"dpid": 1, "in_port": 2, "out_port": 1},
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}
        self.installed_routes = defaultdict(set)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        self.logger.info("Switch connected: s%s", datapath.id)
        self._install_base_rules(datapath)
        self._install_all_static_routes()

    def _install_base_rules(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        table_miss = parser.OFPMatch()
        to_controller = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, table_miss, to_controller)

        arp_match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_ARP)
        self._add_flow(datapath, 10, arp_match, to_controller)

    def _install_all_static_routes(self):
        for flow_key in self.ROUTES:
            self._ensure_route_installed(flow_key)

    def _ensure_route_installed(self, flow_key):
        src_ip, dst_ip = flow_key
        host_meta = self.HOSTS[dst_ip]

        for hop in self.ROUTES[flow_key]:
            datapath = self.datapaths.get(hop["dpid"])
            if datapath is None:
                continue

            route_signature = (src_ip, dst_ip, hop["in_port"], hop["out_port"])
            if route_signature in self.installed_routes[hop["dpid"]]:
                continue

            parser = datapath.ofproto_parser
            match = parser.OFPMatch(
                in_port=hop["in_port"],
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=src_ip,
                ipv4_dst=dst_ip,
            )
            actions = [
                parser.OFPActionSetField(eth_dst=host_meta["mac"]),
                parser.OFPActionOutput(hop["out_port"]),
            ]
            self._add_flow(
                datapath,
                self.ROUTE_PRIORITY,
                match,
                actions,
                cookie=self.ROUTE_COOKIE,
            )
            self.installed_routes[hop["dpid"]].add(route_signature)
            self.logger.info(
                "Installed static route %s -> %s on s%s (in_port=%s, out_port=%s)",
                src_ip,
                dst_ip,
                hop["dpid"],
                hop["in_port"],
                hop["out_port"],
            )

    def _add_flow(self, datapath, priority, match, actions, cookie=0, idle_timeout=0, hard_timeout=0):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            cookie=cookie,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        if eth_pkt is None:
            return

        if eth_pkt.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self._flood_packet(msg)
            self.logger.info(
                "ARP packet_in on s%s from %s asking for %s",
                datapath.id,
                arp_pkt.src_ip,
                arp_pkt.dst_ip,
            )
            return

        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        if ipv4_pkt:
            flow_key = (ipv4_pkt.src, ipv4_pkt.dst)
            if flow_key in self.ROUTES:
                self.logger.info(
                    "IPv4 packet_in on s%s for %s -> %s at port %s, reinstalling static route",
                    datapath.id,
                    ipv4_pkt.src,
                    ipv4_pkt.dst,
                    in_port,
                )
                self._remove_route_state(flow_key)
                self._ensure_route_installed(flow_key)
                self._forward_current_packet(msg)
            else:
                self.logger.warning(
                    "Unknown IPv4 flow %s -> %s reached controller on s%s",
                    ipv4_pkt.src,
                    ipv4_pkt.dst,
                    datapath.id,
                )

    def _remove_route_state(self, flow_key):
        src_ip, dst_ip = flow_key
        for dpid, route_signatures in self.installed_routes.items():
            retained = {
                signature
                for signature in route_signatures
                if not (signature[0] == src_ip and signature[1] == dst_ip)
            }
            self.installed_routes[dpid] = retained

    def _flood_packet(self, msg):
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=actions,
            data=None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data,
        )
        datapath.send_msg(out)

    def _forward_current_packet(self, msg):
        datapath = msg.datapath
        pkt = packet.Packet(msg.data)
        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        if ipv4_pkt is None:
            return

        route = self.ROUTES.get((ipv4_pkt.src, ipv4_pkt.dst))
        if not route:
            return

        out_port = None
        for hop in route:
            if hop["dpid"] == datapath.id and hop["in_port"] == msg.match["in_port"]:
                out_port = hop["out_port"]
                break

        if out_port is None:
            return

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=actions,
            data=None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data,
        )
        datapath.send_msg(out)
