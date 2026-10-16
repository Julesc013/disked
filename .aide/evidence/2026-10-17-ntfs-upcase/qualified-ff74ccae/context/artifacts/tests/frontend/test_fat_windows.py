"""Actual allocation-window command, process binding and frontend journeys."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_allocation_window import SparseVolume,window,oracle
from gui_fixture import Gui,U,wait


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return 'sha256:'+h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('exe','fault','worker','worker-fault','root'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--output',type=Path);a=p.parse_args()
    for name in ('exe','fault','worker','worker_fault','root'):setattr(a,name,getattr(a,name).resolve())
    records=[];passed=False
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_FAT_COMMAND_TEST_','DISKED_FAT_TEST_'))}
    def record(name,**data):print('CASE '+name,flush=True);records.append(dict(name=name,**data))
    def execute(name,exe,args,expected=0,data=b'',settings=None):
        callenv=env.copy();callenv.update(settings or {});cmd=[str(exe),*args]
        r=subprocess.run(cmd,input=data,capture_output=True,timeout=20,env=callenv)
        assert r.returncode==expected and not r.stderr,(name,r.returncode,r.stdout,r.stderr)
        values=[json.loads(line) for line in r.stdout.splitlines()]
        record(name,command=subprocess.list2cmdline(cmd),exit_code=r.returncode,output_sha256='sha256:'+hashlib.sha256(r.stdout).hexdigest())
        return values[0]
    def fields(v,first,count,**extra):return dict(view='fat',volume_offset=str(v.offset),volume_bytes=str(v.length),allocation_window=window(first,count),**extra)
    def options(params):
        names=dict(view='--view',volume_offset='--volume-offset',volume_bytes='--volume-bytes',allocation_window='--allocation-window-json',allocation_scan='--allocation-scan',auxiliary_checks='--auxiliary-checks',fat_copy='--fat-copy')
        out=[]
        for k,value in params.items():out += [names[k],json.dumps(value,separators=(',',':')) if isinstance(value,dict) else value]
        return out
    def observe(name,path,params,expected=0,exe=None,settings=None):
        return execute(name,exe or a.exe,['image','inspect',str(path),*options(params),'--json'],expected,settings=settings)
    def stable(response):
        r=copy.deepcopy(response['result']);r['observation'].pop('capture_epoch')
        for key in ('observation_sha256','capture_sha256','context','worker'):r.pop(key)
        r['capture'].pop('capture_domain');return r
    def compare(expected,actual):
        assert expected['status']==actual['status'] and expected['diagnostics']==actual['diagnostics'],(expected,actual)
        assert stable(expected)==stable(actual),(stable(expected),stable(actual))
    try:
        scratch=a.root/'.aide-local';assert scratch.is_dir()
        with tempfile.TemporaryDirectory(prefix='fat-window-product-',dir=scratch) as folder:
            folder=Path(folder);assert folder.resolve().is_relative_to(scratch)
            fixtures=[]
            for bits in (12,16,32):
                for unit in (512,4096):
                    v=SparseVolume(bits,offset=512,unit=unit)
                    v.link(100,101);v.link(101,100);v.link(103,99);v.link(104,125)
                    path=folder/f'{bits}-{unit}.img';v.write(path);before=sha(path);params=fields(v,100,24)
                    observed=observe(f'window-{bits}-{unit}',path,params);obs=observed['result']['observation'];w=obs['allocation_window']
                    for key,value in oracle(v,100,24).items():
                        actual=w[key];actual={k:int(n) for k,n in actual.items()} if isinstance(value,dict) else int(actual)
                        assert value==actual,(key,value,actual)
                    assert w['scope']=='explicit-cluster-window' and w['coverage_complete'] and w['comparison_complete']
                    assert not w['all_volume_coverage'] and not w['unreferenced_allocation_qualified']
                    assert obs['allocation_scope']=='observed-tree-and-allocation-window' and not obs['filesystem_health_qualified']
                    assert observed['result']['worker']['worker']['observation']=='exited' and observed['operation_id'] is None
                    wire=dict(schema='org.disked.request/1',request_id='window',command='image.inspect',parameters=dict(path=str(path),**params),required_features=[])
                    actual=execute(f'stdio-{bits}-{unit}',a.exe,['protocol','serve','--json'],data=json.dumps(wire).encode())
                    compare(observed,actual);assert sha(path)==before;fixtures.append((path,v,observed))
            # A real larger file: only the selected table pages are captured.
            large=SparseVolume(32,offset=512,clusters=1000000);large.link(800000,800003);large.link(800003,0x0fffffff)
            path=folder/'large.img';large.write(path);before=sha(path)
            value=observe('native-large-window',path,fields(large,800000,1024))
            w=value['result']['observation']['allocation_window'];assert w['scanned_clusters']=='1024' and w['volume_clusters']=='1000000'
            assert w['coverage_complete'] and not w['all_volume_coverage'];assert int(value['result']['capture']['reread_bytes'])<32768
            assert sha(path)==before
            path,v,_=fixtures[0];params=fields(v,100,24)
            value=observe('outside-geometry',path,fields(v,v.g['clusters']+1,2),expected=4)
            assert value['diagnostics'][0]['code']=='fat_capture_incomplete'
            assert value['result']['observation']['allocation_window']['diagnostics']==['fat_allocation_window_range']
            from test_fat_auxiliary import MetadataVolume
            aux=MetadataVolume(32,offset=512,count=24);aux_path=folder/'aux-window.img';aux.write(aux_path)
            value=observe('window-does-not-qualify-fsinfo',aux_path,fields(aux,100,24,auxiliary_checks='yes'))
            info=value['result']['observation']['auxiliary_checks']['fsinfo']
            assert not info['count_comparison_applicable'] and info['free_count_matches'] is None
            missing=folder/'missing.img'
            invalid=[dict(first_cluster='1',clusters='1'),dict(first_cluster='2',clusters='0'),dict(first_cluster='2',clusters='8193'),
                dict(first_cluster='268435447',clusters='1'),dict(first_cluster='01',clusters='1'),dict(first_cluster='2'),
                dict(first_cluster='2',clusters='1',extra='x'),dict(first_cluster='2',clusters=1)]
            for n,w in enumerate(invalid):
                observe('invalid-before-open-'+str(n),missing,dict(params,allocation_window=w),expected=2,exe=a.fault,settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            observe('conflict-before-open',missing,dict(params,allocation_scan='yes'),expected=2,exe=a.fault,settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            execute('map-window-before-open',a.fault,['image','inspect',str(missing),'--allocation-window-json',json.dumps(window(2,1)),'--json'],2,settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            whole=SparseVolume(12);whole_path=folder/'whole.img';whole.write(whole_path);whole_params=fields(whole,2,whole.g['clusters'])
            value=observe('whole-window',whole_path,whole_params)
            assert value['result']['observation']['allocation_window']['unreferenced_allocation_qualified']
            value=observe('changed-withdraws-applicability',whole_path,whole_params,4,a.fault,{'DISKED_FAT_COMMAND_TEST_VERIFY_CHANGED':'1'})
            assert not value['result']['observation']['allocation_window']['unreferenced_allocation_qualified']
            assert 'fat_source_changed' in [d['code'] for d in value['diagnostics']]
            observe('normal-ignores-change-fixture',whole_path,whole_params,settings={'DISKED_FAT_COMMAND_TEST_VERIFY_CHANGED':'1'})
            # Independent parent frame reconstruction and interval input binding.
            req=dict(op='file',path=str(whole_path),offset=str(whole.offset),length=str(whole.length),allocation_window=window(100,20))
            def worker(name,request,exe=None):return execute(name,exe or a.worker,[],data=(json.dumps(request)+'\n').encode())
            value=worker('owned-window-snapshot',req);assert value['has_snapshot'] and value['retained_unchanged']
            frame=worker('pure-window-frame',dict(req,mode='frame'))['frame']
            for key,item in [('all_volume_coverage',True),('unreferenced_allocation_qualified',True),('first_cluster','101')]:
                forged=copy.deepcopy(frame);forged['result']['observation']['allocation_window'][key]=item
                assert 'error' in worker('reject-window-claim-'+key,dict(req,mode='verify',replace=forged))
            assert 'error' in worker('reject-window-input-swap',dict(req,mode='verify',replace=frame,allocation_window=window(101,20)))
            changed=worker('worker-recapture-window',dict(req,allocation_window=window(2,whole.g['clusters']),fixture=dict(capture_fault='verify_changed')),a.worker_fault)
            assert changed['has_snapshot'] and not changed['result']['observation']['allocation_window']['unreferenced_allocation_qualified']
            # Actual native frontend journeys per format, including inert review.
            for path,v,expected in (fixtures[0],fixtures[2],fixtures[4]):
                params=fields(v,100,24);before=sha(path);names={p.name for p in folder.iterdir()}
                g=Gui(a.exe,['--gui','image','inspect',str(path),*options(params)],render=True)
                try:
                    assert not U.IsWindowEnabled(g.child(110));g.click(109)
                    reviewed=g.details();assert reviewed.get('reviewed') is True,reviewed
                    g.click(110)
                    actual=wait(lambda:g.details() if 'status' in g.details() else None)
                    compare(expected,actual);record('gui-'+path.name,response=actual,native=g.observation())
                finally:g.close()
                assert g.code==0 and g.created_files==[]
                for frontend in ('tui','shell'):
                    report=folder/'console.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                    cmd=[sys.executable,str(a.root/'tests/frontend/image_console_fixture.py'),str(a.exe),frontend,'image.inspect',str(path),'-',str(report),json.dumps(options(params))]
                    result=subprocess.run(cmd,cwd=folder,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=30)
                    actual=json.loads(report.read_bytes());assert result.returncode==0,actual
                    compare(expected,actual['response']);record(frontend+'-'+path.name,observation=actual);report.unlink()
                assert sha(path)==before and {p.name for p in folder.iterdir()}==names
        passed=True
    finally:
        if a.output:a.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FAT window commands PASS '+str(len(records)),flush=True)


if __name__=='__main__':main()
