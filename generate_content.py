"""Generate deterministic, synthetic binary fixtures (extensions are illustrative)."""
import argparse
import hashlib
import json
from pathlib import Path

def generate(root='content',scale=1):
    root = Path(root)
    root.mkdir(parents=True,exist_ok=True)
    manifest = {}
    for name,mb in [('video.mp4',16),('image.jpg',1),('document.pdf',2),('music.mp3',4)]:
        block = hashlib.sha256(('SmartCDN synthetic '+name).encode()).digest()*2048
        path = root/name
        with path.open('wb') as stream:
            for _ in range(max(1,int(mb*16*scale))):
                stream.write(block)
        with path.open('rb') as stream:
            manifest[name] = dict(bytes=path.stat().st_size,sha256=hashlib.file_digest(stream,'sha256').hexdigest())
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',default='content'); p.add_argument('--scale',type=float,default=1)
    a=p.parse_args(); generate(a.root,a.scale)
