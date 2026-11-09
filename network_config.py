"""Shared addressing and physical port map; keep link order aligned with topology.py."""
VIP = '10.0.0.100'
VMAC = '02:00:00:00:01:00'
PORT = 5000
LINKS = [(1,2,50),(1,3,30),(1,4,30),(2,5,40),(2,6,40),
         (3,5,20),(4,6,20),(3,4,10),(5,6,10)]
HOSTS = {}
for i in range(1,5):
    HOSTS[f'10.0.0.{10+i}'] = {'name':f'srv{i}', 'switch':3 if i<=2 else 4,
        'port':(i-1)%2+1, 'mac':f'02:00:00:00:00:{10+i:02x}'}
for i in range(1,7):
    HOSTS[f'10.0.0.{20+i}'] = {'name':f'c{i}', 'switch':5 if i<=3 else 6,
        'port':(i-1)%3+1, 'mac':f'02:00:00:00:00:{20+i:02x}'}
SERVERS = list(HOSTS)[:4]
LINK_PORTS = {}
next_port = {1:1,2:1,3:3,4:3,5:4,6:4}
for a,b,bw in LINKS:
    LINK_PORTS[a,b] = (next_port[a],bw)
    LINK_PORTS[b,a] = (next_port[b],bw)
    next_port[a] += 1
    next_port[b] += 1
