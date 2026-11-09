"""Run in c1 namespace: real TCP health probes and server byte counter deltas."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import time
from network_config import SERVERS
from protocol import read_header,send_header

def probe(ip):
    try:
        with socket.create_connection((ip,5000),timeout=.7) as sock:
            send_header(sock,{'op':'health'})
            with sock.makefile('rb') as stream:
                return ip,read_header(stream)
    except (OSError,ValueError):
        return ip,{'healthy':False}

def main():
    p=argparse.ArgumentParser(); p.add_argument('output'); args=p.parse_args()
    path=Path(args.output); previous={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        while True:
            now=time.time(); servers=dict(pool.map(probe,SERVERS))
            for ip,state in servers.items():
                old=previous.get(ip)
                state['mbps']=max(0,state.get('bytes',0)-old[1])*8/1e6/max(now-old[0],.01) if old and state.get('healthy') else 0
                if state.get('healthy'):
                    previous[ip]=(now,state['bytes'])
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(timestamp=time.time(),servers=servers)))
            temp.replace(path)
            time.sleep(1)

if __name__=='__main__':
    main()
