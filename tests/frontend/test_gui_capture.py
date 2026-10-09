"""Real retained frame regression and owned native capture qualification.

PNG decoding only reads repository-produced filter-zero RGB fixtures; this is
not a product image decoder, text recognizer or general visual qualification.
"""
import argparse,ctypes as C,hashlib,json,shutil,struct,subprocess,sys,tempfile,zlib
from contextlib import contextmanager
from ctypes import wintypes as W
from pathlib import Path
from gui_fixture import Gui,U,capture_client_content

@contextmanager
def capture_directory(root):
    root=root.resolve();root.mkdir(exist_ok=True)
    path=Path(tempfile.mkdtemp(prefix='disked-gui-capture-',dir=root))
    assert path.resolve().is_relative_to(root)
    try:yield path
    except BaseException:
        print('Failed capture fixture retained: '+str(path),file=sys.stderr);raise
    else:
        assert path.resolve().is_relative_to(root)
        shutil.rmtree(path)

def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def png(path):
    data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n';offset=8;compressed=bytearray();size=None
    while offset<len(data):
        count=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];body=data[offset+8:offset+8+count]
        assert zlib.crc32(kind+body)&0xffffffff==struct.unpack('>I',data[offset+8+count:offset+12+count])[0]
        if kind==b'IHDR':
            w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',body)
            assert 0<w<=4096 and 0<h<=4096 and (depth,color,compression,filtering,interlace)==(8,2,0,0,0);size=(w,h)
        elif kind==b'IDAT':compressed.extend(body)
        offset+=12+count
    assert size;w,h=size;raw=zlib.decompress(compressed);assert len(raw)==h*(1+w*3)
    pixels=bytearray(w*h*4)
    for y in range(h):
        start=y*(1+w*3);assert raw[start]==0;row=raw[start+1:start+1+w*3];target=y*w*4
        pixels[target:target+w*4:4]=row[2::3];pixels[target+1:target+w*4:4]=row[1::3];pixels[target+2:target+w*4:4]=row[0::3]
    return w,h,bytes(pixels)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--product',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--evidence',type=Path);args=parser.parse_args()
    root=args.root.resolve();exe=args.product.resolve();checks=[];captures=[]
    def check(name,passed):assert passed,name;checks.append(dict(name=name,passed=True))
    fixtures=root/'tests/frontend/fixtures/gui-capture';manifest=json.loads((fixtures/'fixtures.json').read_bytes())
    for name,expected in [('frame-only.png',False),('redrawn-client.png',True)]:
        path=fixtures/name;check(name+'-exact-fixture',sha(path.read_bytes())==manifest['files'][name]);w,h,body=png(path)
        box=(16,48,w-16,h-16) # Conservative known client interior of these retained fixtures.
        if not expected:check('old-whole-window-threshold-accepted-frame',len(set(struct.iter_unpack('<I',body)))>10)
        check(name+'-client-classification',capture_client_content(body,w,h,box)==expected)
    alpha=bytes([0,0,0,0,0,0,0,255]);check('unused-alpha-is-not-painted-content',not capture_client_content(alpha,2,1,(0,0,2,1)))
    # The output folder belongs to this harness; nothing touches physical media.
    with capture_directory(root/'.aide-local') as output:
        for name,argv in [('inventory',[]),('review',['--gui','target','inspect','fake:alpha@1']),('minimum',['--gui','target','inspect','fake:alpha@1'])]:
            ui=Gui(exe,argv,render=True)
            try:
                if name!='inventory':ui.click(109);check(name+'-review-inert',ui.details()['reviewed'] and ui.text(110)=='&Submit reviewed' and U.IsWindowEnabled(ui.child(110)))
                if name=='minimum':assert U.SetWindowPos(ui.window,None,0,0,640,480,0x16)
                before=ui.details()
                for index in range(2):
                    path=output/(name+'-'+str(index)+'.png');geometry=ui.screenshot(path);w,h,body=png(path)
                    check(name+'-actual-client-'+str(index),(w,h)==(geometry['width'],geometry['height']) and capture_client_content(body,w,h,geometry['client_box']))
                    if name!='inventory':
                        frame=W.RECT();button=W.RECT();assert U.GetWindowRect(ui.window,C.byref(frame)) and U.GetWindowRect(ui.child(110),C.byref(button))
                        box=(button.left-frame.left+6,button.top-frame.top+6,button.right-frame.left-6,button.bottom-frame.top-6)
                        check(name+'-actual-caption-pixels-'+str(index),capture_client_content(body,w,h,box))
                    check(name+'-capture-not-submission-'+str(index),ui.details()==before)
                    record=dict(name=name+'-'+str(index),geometry=geometry,sha256=sha(path.read_bytes()))
                    if args.evidence:
                        args.evidence.parent.mkdir(parents=True,exist_ok=True);selected=args.evidence.parent/path.name;shutil.copyfile(path,selected);record['path']=str(selected)
                    captures.append(record)
            finally:ui.close();assert ui.code==0 and not ui.error and not ui.output
    result=dict(passed=True,checks=len(checks),observations=checks,captures=captures,
        source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root)),executable_sha256=sha(exe.read_bytes()),
        scope='Actual owned Windows inventory/review/minimum captures, retained frame-only regression and DIB alpha guard; no layout/accessibility/text-recognition/storage qualification')
    if args.evidence:args.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('captures','observations')}))
if __name__=='__main__':main()
