"""OpenFlow message tests use real OS-Ken parsers without network privileges."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
try:
    from os_ken.ofproto import ofproto_v1_3 as ofp,ofproto_v1_3_parser as parser
    from os_ken.lib.packet import packet,ethernet,ipv4,tcp,arp
    from simple_switch_13 import SimpleSwitch13
    AVAILABLE=True
except ImportError:
    AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'Run controller tests using sdn-env/bin/python')
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,SMARTCDN_RESULTS=self.directory.name),patch('simple_switch_13.hub.spawn'):
            self.app=SimpleSwitch13()
        self.sent={}
        for i in range(1,7):
            self.sent[i]=[]
            self.app.datapaths[i]=SimpleNamespace(id=i,ofproto=ofp,ofproto_parser=parser,
                send_msg=self.sent[i].append)
        self.app.health={ip:dict(healthy=True,active=0,mbps=0) for ip in ['10.0.0.11','10.0.0.12','10.0.0.13','10.0.0.14']}

    def tearDown(self): self.directory.cleanup()

    def event(self,reverse=False):
        data=packet.Packet()
        data.add_protocol(ethernet.ethernet(src='02:00:00:00:00:15',dst='02:00:00:00:01:00',ethertype=0x800))
        if reverse:
            data.add_protocol(ipv4.ipv4(src='10.0.0.11',dst='10.0.0.21',proto=6))
            data.add_protocol(tcp.tcp(src_port=5000,dst_port=32100,bits=tcp.TCP_SYN|tcp.TCP_ACK))
        else:
            data.add_protocol(ipv4.ipv4(src='10.0.0.21',dst='10.0.0.100',proto=6))
            data.add_protocol(tcp.tcp(src_port=32100,dst_port=5000,bits=tcp.TCP_SYN,seq=123))
        data.serialize()
        return SimpleNamespace(msg=SimpleNamespace(data=data.data,datapath=self.app.datapaths[3 if reverse else 5],match={'in_port':1}))

    def test_vip_nat_bidirectional_and_serialization(self):
        self.app.packet_in(self.event())
        self.assertEqual(self.app.sessions['10.0.0.21',32100]['server'],'10.0.0.11')
        rules=[m for m in self.sent[5] if isinstance(m,parser.OFPFlowMod)]
        vip=next(m for m in rules if m.priority==110)
        self.assertEqual(vip.match['ipv4_dst'],'10.0.0.100')
        fields=[a.key for a in vip.instructions[0].actions if isinstance(a,parser.OFPActionSetField)]
        self.assertIn('ipv4_dst',fields)
        reverse=next(m for m in rules if m.match.get('ipv4_src')=='10.0.0.11')
        self.assertTrue(any(getattr(a,'value',None)=='10.0.0.100' for a in reverse.instructions[0].actions))
        self.app.packet_in(self.event(True))
        for messages in self.sent.values():
            for message in messages:
                message.serialize()
                self.assertGreater(len(message.buf),8)

    def test_link_reroute_and_no_flood(self):
        self.app.packet_in(self.event())
        self.app.down_ports.add((5,5)) # s5 to s3
        self.app.invalidate()
        self.app.packet_in(self.event())
        for messages in self.sent.values():
            for message in messages:
                actions=getattr(message,'actions',[])
                self.assertFalse(any(getattr(a,'port',None)==ofp.OFPP_FLOOD for a in actions))
        self.assertEqual(self.app.decisions,1) # stable server for the existing connection

    def test_proxy_arp_vip(self):
        data=packet.Packet()
        data.add_protocol(ethernet.ethernet(src='02:00:00:00:00:15',dst='ff:ff:ff:ff:ff:ff',ethertype=0x806))
        data.add_protocol(arp.arp(opcode=1,src_mac='02:00:00:00:00:15',src_ip='10.0.0.21',dst_ip='10.0.0.100'))
        data.serialize()
        self.app.packet_in(SimpleNamespace(msg=SimpleNamespace(data=data.data,datapath=self.app.datapaths[5],match={'in_port':1})))
        out=self.sent[5][-1]
        reply=packet.Packet(out.data).get_protocol(arp.arp)
        self.assertEqual(reply.opcode,2); self.assertEqual(reply.src_ip,'10.0.0.100')
        self.assertEqual(out.actions[0].port,1)

if __name__=='__main__': unittest.main()
