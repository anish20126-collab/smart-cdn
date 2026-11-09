"""Threaded binary content server with in-band health/load telemetry."""
import argparse
import hashlib
from pathlib import Path
import socketserver
import threading
import time
from protocol import read_header, send_header

class ContentServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    def __init__(self,address,name,root,rate=0):
        self.name,self.root,self.rate = name,Path(root).resolve(),rate
        self.lock = threading.Lock()
        self.active = self.total = self.sent = 0
        self.started = time.monotonic()
        self.catalog = {}
        for path in self.root.iterdir():
            if path.is_file() and path.suffix in {'.mp4','.jpg','.pdf','.mp3'}:
                with path.open('rb') as stream:
                    self.catalog[path.name] = (path.stat().st_size,hashlib.file_digest(stream,'sha256').hexdigest())
        super().__init__(address,Handler)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(15)
        server = self.server
        counted = False
        try:
            with self.request.makefile('rb') as stream:
                request = read_header(stream)
            if request.get('op') == 'health':
                with server.lock:
                    status = dict(healthy=True,server=server.name,active=server.active,
                                  requests=server.total,bytes=server.sent,uptime=time.monotonic()-server.started)
                send_header(self.request,status)
                return
            name = request.get('name','')
            if name not in server.catalog or Path(name).name != name:
                send_header(self.request,{'ok':False,'error':'Content not found'})
                return
            size,digest = server.catalog[name]
            with server.lock:
                server.active += 1
                server.total += 1
                counted = True
            send_header(self.request,dict(ok=True,size=size,sha256=digest,server=server.name))
            began = time.monotonic()
            sent = 0
            with (server.root/name).open('rb') as content:
                while chunk := content.read(65536):
                    self.request.sendall(chunk)
                    sent += len(chunk)
                    with server.lock:
                        server.sent += len(chunk)
                    if server.rate:
                        time.sleep(max(0,sent/server.rate-(time.monotonic()-began)))
        except (OSError,ValueError,TypeError) as exc:
            print(f'{server.name}: {exc}',flush=True)
        finally:
            if counted:
                with server.lock:
                    server.active -= 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--root',default='content')
    parser.add_argument('--bind',default='0.0.0.0')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--rate',type=float,default=0,help='Optional bytes/sec per transfer')
    args = parser.parse_args()
    with ContentServer((args.bind,args.port),args.name,args.root,args.rate) as server:
        print(f'{args.name} listening on {args.bind}:{args.port}',flush=True)
        server.serve_forever()

if __name__ == '__main__':
    main()
