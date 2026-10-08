import ctypes as C,json,struct,subprocess,sys,tempfile,time,zlib
from ctypes import wintypes as W
from pathlib import Path
root=Path(sys.argv[1]).resolve();E=Path(sys.argv[2]).resolve();exe=root/'build/windows-bootstrap/Release/disked.exe'
sys.path.insert(0,str(root/'tests/frontend'));from gui_fixture import Gui,U,bind,wait
bind(U,'RedrawWindow',W.BOOL,[W.HWND,C.POINTER(W.RECT),C.c_void_p,W.UINT])
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def pixels(path):
    raw=path.read_bytes();at=8;data=b''
    while at<len(raw):
        n=int.from_bytes(raw[at:at+4],'big');kind=raw[at+4:at+8];body=raw[at+8:at+8+n];at+=n+12
        if kind==b'IHDR':width,height=struct.unpack('>II',body[:8])
        elif kind==b'IDAT':data+=body
    rows=zlib.decompress(data);samples=bytearray()
    for y in range(45,height-10):
        begin=y*(width*3+1);assert rows[begin]==0;samples.extend(rows[begin+1+10*3:begin+1+(width-10)*3])
    rgb=set(struct.iter_unpack('BBB',samples));black=sum(1 for v in struct.iter_unpack('BBB',samples) if v==(0,0,0))
    return dict(client_colors=len(rgb),client_black_fraction=black/(len(samples)//3),width=width,height=height)
root.joinpath('.aide-local').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'.aide-local',prefix='review-paint-') as scratch:
    folder=Path(scratch);source=folder/'source.img';source.write_bytes(bytes(range(256))*16);state=folder/'state';state.mkdir()
    dest=folder/'copy.img';m=folder/'copy.map'
    p=subprocess.run([str(exe),'image','acquire','prepare',str(source),str(dest),'--map',str(m),'--state-dir',str(state),'--json'],capture_output=True,cwd=root,timeout=15)
    assert p.returncode==0 and not p.stderr;definition=json.loads(p.stdout)['result'];g=dict(phase='execute',definition=definition['definition'],definition_digest=definition['definition_digest'],allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
    args=['--gui','image','acquire','execute','--definition-json',canonical(g['definition']).decode(),'--definition-digest',g['definition_digest']]
    args += ['--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']
    ui=Gui(exe,args,render=True)
    try:
        ui.click(109);assert ui.details()['reviewed'] and ui.details()['parameters']==g and ui.details()['expected_revision'] is None
        def capture():
            assert U.RedrawWindow(ui.window,None,None,0x0001|0x0004|0x0080|0x0100)
            path=E/'gui-acquisition-execute-review-redrawn.png';ui.screenshot(path);v=pixels(path)
            return v if v['client_colors']>10 and v['client_black_fraction']<.9 else None
        observed=wait(capture,8);observed.update(phase='execute',reviewed=True,submitted=False,source_revision='54328453e355b0522e4cb2581a8887247a18efd8')
        assert not dest.exists() and not m.exists() and not list(state.iterdir())
    finally:ui.close()
    assert ui.code==0 and not ui.error
(E/'visual-review.json').write_bytes(json.dumps(observed,indent=2).encode()+b'\n')
print(json.dumps(observed))
