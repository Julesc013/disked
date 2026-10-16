"""Actual FAT image command/frontends over independently generated ordinary files."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_capture import Volume,short,slots,code_units
from test_fat_auxiliary import MetadataVolume
from gui_fixture import Gui,U,wait
from test_image_commands import Gate


def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('exe','fault','root'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--output',type=Path);args=p.parse_args()
    args.exe=args.exe.resolve();args.fault=args.fault.resolve();args.root=args.root.resolve()
    records=[];passed=False
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_FAT_COMMAND_TEST_') and not k.startswith('DISKED_FAT_TEST_')}
    def record(name,**data):print('CASE '+name,flush=True);records.append(dict(name=name,**data))
    def launch(name,argv,expected=0,diagnostic=None,exe=None,data=b'',settings=None):
        callenv=env.copy();callenv.update(settings or {})
        cmd=[str(exe or args.exe),*argv]
        result=subprocess.run(cmd,input=data,capture_output=True,timeout=20,env=callenv)
        assert result.returncode==expected,(name,result.returncode,result.stdout,result.stderr)
        assert not result.stderr,(name,result.stderr)
        values=[json.loads(line) for line in result.stdout.splitlines()]
        if diagnostic:assert diagnostic in [d['code'] for d in values[0]['diagnostics']],(name,values)
        for value in values:assert value['operation_id'] is None
        record(name,command=subprocess.list2cmdline(cmd),exit_code=result.returncode,output_sha256=digest(result.stdout))
        return values
    def controls(volume,lookup=None,**fields):
        values=dict(view='fat',volume_offset=str(volume.offset),volume_bytes=str(volume.length),**fields)
        if lookup is not None:values.update(name_code_page='437',lookup=lookup)
        return values
    def options(values):
        names=dict(view='--view',volume_offset='--volume-offset',volume_bytes='--volume-bytes',fat_copy='--fat-copy',
            allocation_scan='--allocation-scan',auxiliary_checks='--auxiliary-checks',name_code_page='--name-code-page',lookup='--lookup-json')
        out=[]
        for key,value in values.items():out += [names[key],json.dumps(value,ensure_ascii=False,separators=(',',':')) if isinstance(value,dict) else value]
        return out
    def observe(name,path,fields,**kw):return launch(name,['--json','image','inspect',str(path),*options(fields)],**kw)[0]
    def wire(params,id='fat:req',**extra):return dict(schema='org.disked.request/1',request_id=id,command='image.inspect',parameters=params,required_features=[],**extra)
    def encode(value):return json.dumps(value,ensure_ascii=False).encode('utf-8')
    def stable(response):
        result=copy.deepcopy(response['result']);obs=result['observation'];obs.pop('capture_epoch')
        result.pop('observation_sha256');result.pop('capture_sha256');result.pop('context');result.pop('worker')
        capture=result['capture'];capture.pop('capture_domain')
        # Attempt fields and their digests differ; interpreted rows/source data must agree.
        return result
    def compare(expected,actual):
        assert expected['status']==actual['status'] and expected['diagnostics']==actual['diagnostics'],(expected,actual)
        assert stable(expected)==stable(actual),(stable(expected),stable(actual))
    scratch=args.root/'.aide-local';scratch.mkdir(exist_ok=True)
    assert scratch.resolve().is_relative_to(args.root)
    try:
        with tempfile.TemporaryDirectory(prefix='fat-command-',dir=scratch) as folder:
            folder=Path(folder);assert folder.resolve().is_relative_to(scratch.resolve())
            fixtures=[]
            for bits in (12,16,32):
                for unit in (512,4096):
                    volume=MetadataVolume(bits,unit=unit,offset=512);item=short();name='A long name.txt'
                    long,_=slots(code_units(name),item);volume.directory([long,bytes(item)])
                    path=folder/f'{bits}-{unit}.img';volume.write(path);fixtures.append((path,volume))
                    before=digest(path.read_bytes());fields=controls(volume,dict(directory='0',names=[name,'FILE.TXT','missing']),auxiliary_checks='yes')
                    value=observe(f'fat-{bits}-{unit}',path,fields)
                    result=value['result'];assert result['schema']=='org.disked.fat-image-observation/1'
                    assert result['provider']=='provider.image.fat.prototype/1' and result['scope']=='ordinary-local-file-fat'
                    assert result['observation']['geometry']['bits']==str(bits)
                    assert result['worker']['worker']['observation']=='exited'
                    assert int(result['context']['pid'])>0 and int(result['context']['created'])>0
                    assert result['capture']['observed_stable'] and not result['capture']['whole_file_hashed']
                    assert [q['status'] for q in result['observation']['namespace']['queries']]==['unique','unique','not_found']
                    node=result['observation']['nodes']['items'][1]
                    assert node['name_oem']==item[:11].hex();assert node['source_record_offset']==str(volume.offset+volume.root_offset+len(long))
                    assert node['long_name']['units'][:len(code_units(name))]==list(map(str,code_units(name)))
                    assert not result['authorizes_effects'] and not result['storage_consumer_qualified']
                    params=dict(path=str(path),**fields)
                    protocol=launch('stdio-'+path.name,['protocol','serve','--json'],data=encode(wire(params)))[0]
                    compare(value,protocol);assert digest(path.read_bytes())==before
            path,volume=fixtures[0];fields=controls(volume);plain=observe('fat-base',path,fields)
            opt=launch('option-placement',['--json',*options(fields),'image','inspect',str(path)])[0];compare(plain,opt)
            for page in ('437','850','932'):
                fields=controls(volume,name_code_page=page);value=observe('page-'+page,path,fields)
                assert value['result']['observation']['namespace']['consumer_binding']['code_page']==page
            value=observe('allocation-and-copy',path,controls(volume,fat_copy='1',allocation_scan='yes',auxiliary_checks='yes'))
            assert value['result']['observation']['fat_copy']=='1'
            assert value['result']['observation']['allocation_scan']['coverage_complete']
            assert value['result']['observation']['allocation_scan']['comparison_complete']
            empty=folder/'invalid.img';empty.write_bytes(bytes(1024));invalid=observe('invalid-format',empty,dict(view='fat',volume_offset='0',volume_bytes='1024'),expected=4,diagnostic='fat_capture_incomplete')
            assert invalid['result']['observation']['nodes']['total']=='0'
            damaged=Volume();damaged.directory([bytes(short(name=b'A       TXT',cluster=3,size=600))]);damaged.link(3,3)
            broken=folder/'cycle.img';damaged.write(broken)
            value=observe('chain-cycle',broken,controls(damaged),expected=4,diagnostic='fat_capture_incomplete')
            assert not value['result']['observation']['selected_tree_complete']
            large=Volume(32);large.chain(list(range(2,11)))
            large.directory([bytes(short(name=f'F{n:07d}TXT'.encode())) for n in range(130)])
            many=folder/'nodes.img';large.write(many)
            value=observe('bounded-tree',many,controls(large),expected=4,diagnostic='fat_capture_incomplete')
            assert not value['result']['observation']['selected_tree_complete']
            # Full analysis remains complete when the public projection omits detail rows.
            detailed=Volume(32);rows=[]
            for n in range(80):
                item=short(name=f'L{n:07d}TXT'.encode())
                long,_=slots(code_units('界'*246+f'{n:04d}'),item)
                rows.extend([long,bytes(item)])
            directory_bytes=len(b''.join(rows))+32
            detailed.chain(list(range(2,2+(directory_bytes+511)//512)))
            detailed.directory(rows);detail_path=folder/'detail.img';detailed.write(detail_path)
            value=observe('detail-omissions',detail_path,controls(detailed))
            nodes=value['result']['observation']['nodes']
            assert nodes['total']=='81' and int(nodes['omitted'])>0,nodes
            assert value['result']['observation']['selected_tree_complete']
            large_wire=launch('stdio-detail-omissions',['protocol','serve','--json'],data=encode(wire(dict(path=str(detail_path),**controls(detailed)))))[0]
            compare(value,large_wire)
            detail_gui=Gui(args.exe,['--gui','image','inspect',str(detail_path),*options(controls(detailed))],render=True)
            try:
                detail_gui.click(109);detail_gui.click(110)
                actual=wait(lambda:detail_gui.details() if 'status' in detail_gui.details() else None)
                compare(value,actual);record('large-detail-gui',response=actual,native=detail_gui.observation())
            finally:detail_gui.close()
            assert detail_gui.code==0 and detail_gui.created_files==[]
            missing=folder/'missing.img'
            valid=controls(volume);invalid_controls=[dict(view='fat'),dict(view='fat',volume_offset='0'),dict(view='fat',volume_offset='0',volume_bytes='0'),
                dict(valid,volume_offset=str(2**64-1)),dict(valid,fat_copy=str(2**32)),dict(valid,name_code_page='1252'),dict(valid,allocation_scan='true'),
                dict(view='map',volume_offset='0'),dict(valid,lookup=dict(directory='0',names=['x'])),
                dict(valid,name_code_page='437',lookup=dict(directory='128',names=['x'])),dict(valid,name_code_page='437',lookup=dict(directory='0',names=['🙂'*128]))]
            for n,patch in enumerate(invalid_controls):
                launch('invalid-before-source-'+str(n),['--json','image','inspect',str(missing),*options(patch)],expected=2,exe=args.fault,
                    settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            launch('inapplicable-logical-unit',['--json','image','inspect',str(missing),*options(valid),'--logical-block-bytes','512'],expected=2,exe=args.fault,
                settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            for argv in (['--help'],['image','inspect','--help'],['build','inspect'],['commands']):
                launch('essential-before-source',['--json',*argv],exe=args.fault,settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            params=dict(path=str(missing),**valid)
            launch('unexpected-revision',['protocol','serve','--json'],expected=2,diagnostic='unexpected_revision',exe=args.fault,data=encode(wire(params,expected_revision='sha256:'+'0'*64)),settings={'DISKED_FAT_COMMAND_TEST_OPEN_GUARD':'1'})
            observe('missing-source',missing,valid,expected=3,diagnostic='fat_source_open')
            observe('outside-source',path,dict(valid,volume_bytes=str(volume.length+1000)),expected=3,diagnostic='fat_capture_window')
            for flag,code in [('VERIFY_CHANGED','fat_source_changed'),('VERIFY_ERROR','fat_capture_incomplete')]:
                value=observe('fault-'+flag,path,valid,expected=4,diagnostic=code,exe=args.fault,settings={'DISKED_FAT_COMMAND_TEST_'+flag:'1'})
                assert not value['result']['capture']['observed_stable']
                observe('normal-ignores-'+flag,path,valid,settings={'DISKED_FAT_COMMAND_TEST_'+flag:'1'})
            mixed=observe('partial-and-changed',broken,controls(damaged),expected=4,diagnostic='fat_source_changed',exe=args.fault,
                settings={'DISKED_FAT_COMMAND_TEST_VERIFY_CHANGED':'1'})
            assert 'fat_capture_incomplete' in [d['code'] for d in mixed['diagnostics']]
            observe('invalid-child-reply',path,valid,expected=6,diagnostic='fat_reader_validation_unresolved',exe=args.fault,settings={'DISKED_FAT_COMMAND_TEST_INVALID_REPLY':'1'})
            # One native GUI/TUI/shell journey per FAT family, through the same descriptor controls.
            for path,volume in (fixtures[0],fixtures[2],fixtures[4]):
                fields=controls(volume);expected=observe('frontend-basis-'+path.name,path,fields)
                before=digest(path.read_bytes());names={p.name for p in folder.iterdir()}
                gui=Gui(args.exe,['--gui','image','inspect',str(path),*options(fields)],render=True)
                try:
                    assert not U.IsWindowEnabled(gui.child(110));gui.click(109);assert gui.details()['reviewed'];gui.click(110)
                    actual=wait(lambda:gui.details() if 'status' in gui.details() else None)
                    compare(expected,actual);record('gui-'+path.name,response=actual,native=gui.observation())
                finally:gui.close()
                assert gui.code==0 and gui.created_files==[]
                for frontend in ('tui','shell'):
                    report=folder/'console.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                    call=[sys.executable,str(args.root/'tests/frontend/image_console_fixture.py'),str(args.exe),frontend,'image.inspect',str(path),'-',str(report),json.dumps(options(fields))]
                    result=subprocess.run(call,cwd=folder,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=30)
                    actual=json.loads(report.read_bytes());assert result.returncode==0,actual
                    compare(expected,actual['response']);record(frontend+'-'+path.name,observation=actual);report.unlink()
                assert digest(path.read_bytes())==before and {p.name for p in folder.iterdir()}==names
            # Controlled callback: soft wait cannot free a still-executing slot or emit a late reply.
            path,volume=fixtures[0];params=dict(path=str(path),**controls(volume));gate=Gate()
            settings=env.copy();settings.update(DISKED_FAT_COMMAND_TEST_GATE='1',DISKED_IMAGE_TEST_GATE=gate.name)
            proc=subprocess.Popen([str(args.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=settings)
            messages=queue.Queue()
            thread=threading.Thread(target=lambda:[messages.put(json.loads(line)) for line in proc.stdout],daemon=True);thread.start()
            def send(value):proc.stdin.write(encode(value)+b'\n');proc.stdin.flush()
            try:
                send(wire(params,'wait'));gate.entered();expired=messages.get(timeout=6)
                assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
                send(wire(params,'busy'));busy=messages.get(timeout=2);assert busy['diagnostics'][0]['code']=='request_resource_limit'
                send(dict(schema='org.disked.request/1',request_id='essential',command='build.inspect',parameters={},required_features=[]))
                assert messages.get(timeout=2)['status']=='completed';gate.release()
                after=None
                for attempt in range(35):
                    time.sleep(.1);send(wire(params,'after:'+str(attempt)));after=messages.get(timeout=3)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit'
                assert after and after['status']=='completed';assert messages.empty()
                proc.stdin.close();assert proc.wait(timeout=8)==6 and not proc.stderr.read()
                record('wait-busy-late-release',expired=expired,busy=busy,after=after)
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                thread.join(timeout=1);proc.stdout.close();proc.stderr.close();gate.close()
        passed=True
    finally:
        if args.output:args.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Shared FAT commands '+('PASS' if passed else 'FAIL')+' '+str(len(records)),flush=True)


if __name__=='__main__':main()
