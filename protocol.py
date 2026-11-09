"""Newline JSON headers followed by exactly the declared number of binary bytes."""
import json
MAX_HEADER = 16384

def send_header(sock, obj):
    sock.sendall(json.dumps(obj,separators=(',',':')).encode()+b'\n')

def read_header(stream):
    line = stream.readline(MAX_HEADER+1)
    if not line.endswith(b'\n') or len(line)>MAX_HEADER:
        raise ValueError('Missing or oversized protocol header')
    value = json.loads(line)
    if not isinstance(value,dict):
        raise ValueError('Header must be an object')
    return value
