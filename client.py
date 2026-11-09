"""Request the virtual service; verify SHA-256 before committing downloaded data."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time
from protocol import read_header,send_header
from network_config import VIP

def fetch(address,name,output=None,port=5000,timeout=20):
    began = time.monotonic()
    result = dict(ok=False,server='',client_port=0,bytes=0,response_s=0,throughput_mbps=0,error='')
    temporary = None
    try:
        with socket.create_connection((address,port),timeout=timeout) as sock:
            result['client_port'] = sock.getsockname()[1]
            send_header(sock,dict(op='get',name=name))
            with sock.makefile('rb') as stream:
                header = read_header(stream)
                if not header.get('ok'):
                    raise ValueError(header.get('error','Server refused request'))
                remaining = int(header['size'])
                if remaining<0:
                    raise ValueError('Invalid content length')
                result['server'] = header['server']
                digest = hashlib.sha256()
                target = None
                if output:
                    path = Path(output)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    temporary = path.with_name(path.name+'.part')
                    target = temporary.open('wb')
                try:
                    while remaining:
                        chunk = stream.read(min(65536,remaining))
                        if not chunk:
                            raise ValueError('Truncated transfer')
                        digest.update(chunk)
                        if target:
                            target.write(chunk)
                        remaining -= len(chunk)
                        result['bytes'] += len(chunk)
                finally:
                    if target:
                        target.close()
                if digest.hexdigest()!=header['sha256']:
                    raise ValueError('SHA-256 mismatch')
                if temporary:
                    temporary.replace(output)
                result['ok'] = True
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result['error'] = str(exc)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    result['response_s'] = time.monotonic()-began
    result['throughput_mbps'] = result['bytes']*8/1e6/max(result['response_s'],1e-9)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('address',nargs='?',default=VIP)
    parser.add_argument('name',nargs='?',default='document.pdf')
    parser.add_argument('--output')
    parser.add_argument('--timeout',type=float,default=20)
    args = parser.parse_args()
    result = fetch(args.address,args.name,args.output,timeout=args.timeout)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['ok'] else 1)

if __name__ == '__main__':
    main()
