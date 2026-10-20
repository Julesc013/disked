"""Opt-in bounded guest-coordinator capture for the fixture's own window."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def capture(window,pid,desktop,width,height):
    root=Path(os.environ['DISKED_WINDOW_CAPTURE_ROOT'])
    if root.resolve()!=Path(os.environ['TEMP']).resolve():raise ValueError('Owned capture temp required')
    nonce=os.environ['DISKED_WINDOW_CAPTURE_NONCE'];ident=uuid.uuid4().hex
    request=root/('window-capture-request-'+ident+'.json')
    response=root/('window-capture-response-'+ident+'.json')
    raw=response.with_suffix('.bgra');ready=response.with_suffix('.ready')
    with request.open('x',encoding='utf-8') as stream:
        json.dump(dict(nonce=nonce,id=ident,window=window,pid=pid,desktop=desktop),stream)
    request.with_suffix('.ready').touch(exist_ok=False)
    until=time.monotonic()+15
    while not ready.exists():
        if time.monotonic()>until:raise TimeoutError('Owned window capture coordinator')
        time.sleep(.02)
    if response.stat().st_size>4096 or raw.stat().st_size>16777216:raise ValueError('Capture response bound')
    value=json.loads(response.read_bytes());body=raw.read_bytes()
    if (value['nonce']!=nonce or value['id']!=ident or value['window']!=window or value['pid']!=pid or
            value['desktop']!=desktop or value['method']!='owned-window-dc' or
            (value['width'],value['height'])!=(width,height) or len(body)!=width*height*4 or
            value['bytes']!=len(body) or value['sha256']!=hashlib.sha256(body).hexdigest()):
        raise ValueError('Capture response identity or pixels differ')
    for path in (raw,response,ready):path.unlink()
    return body
