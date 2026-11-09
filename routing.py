"""Pure, testable routing and selection policy. Rates are measured Mbps."""
import heapq
from network_config import LINK_PORTS, HOSTS, SERVERS

def shortest_path(src, dst, down, rates):
    queue = [(0.0,src,[])]
    seen = set()
    while queue:
        cost,node,path = heapq.heappop(queue)
        if node in seen:
            continue
        path = path+[node]
        if node == dst:
            return cost,path
        seen.add(node)
        for (a,b),(port,capacity) in LINK_PORTS.items():
            if a != node or (a,b) in down or b in seen:
                continue
            reverse_port = LINK_PORTS[b,a][0]
            # Downloads dominate reverse traffic: assess both directions.
            measured = max(rates.get((a,port),0),rates.get((b,reverse_port),0))
            utilization = min(.99,max(0,measured/capacity))
            # Five ms link delay plus serialization/congestion penalty.
            weight = 5 + 100/max(.1,capacity*(1-utilization))
            heapq.heappush(queue,(cost+weight,b,path))
    return float('inf'),[]

def select_server(client, health, down, rates, reservations=None):
    candidates = []
    for server in SERVERS:
        status = health.get(server,{})
        if not status.get('healthy',False):
            continue
        cost,path = shortest_path(HOSTS[client]['switch'],HOSTS[server]['switch'],down,rates)
        if path:
            active = status.get('active',0)+(reservations or {}).get(server,0)
            score = cost + 20*active + 2*status.get('mbps',0)
            candidates.append((score,server,path))
    if not candidates:
        return None
    return min(candidates)
