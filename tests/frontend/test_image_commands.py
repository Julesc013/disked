"""Actual native shared raw-file commands and isolated frontend journeys."""
import argparse
import ctypes as C
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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus'))
import partition_images as corpus
from gui_fixture import Gui,U,WP,wait

def main():
    p=argparse.ArgumentParser()
    for name in ['exe','fault','probe','root']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--evidence',type=Path);p.add_argument('--validate-schemas',action='store_true');args=p.parse_args()
    for name in ['exe','fault','probe','root']:setattr(args,name,getattr(args,name).resolve())
    records=[];bundle=None
    if args.validate_schemas:
        sys.path.insert(0,str(args.root/'spec/tools'));import specctl;bundle=specctl.Bundle(args.root/'spec')
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_IMAGE_TEST_')}
    def record(name,**data):print('CASE '+ascii(name),flush=True);records.append(dict(name=name,**data))
    def launch(name,argv,code=0,diagnostic=None,exe=None,data=b'',fault=None,cwd=None):
        callenv=env.copy()
        if fault:callenv['DISKED_IMAGE_TEST_'+fault]='1'
        actual=subprocess.run([str(exe or args.exe),*argv],cwd=cwd,env=callenv,input=data,capture_output=True,timeout=15)
        assert actual.returncode==code,(name,actual.returncode,actual.stdout,actual.stderr)
        assert actual.stderr==b'',(name,actual.stderr)
        values=[json.loads(line) for line in actual.stdout.splitlines()]
        for value in values:
            if bundle:bundle.validate('urn:disked:schema:response:1',value)
            assert value['operation_id'] is None
        if diagnostic:assert diagnostic in [d['code'] for d in values[0]['diagnostics']],(name,values)
        record(name,command=subprocess.list2cmdline([str(exe or args.exe),*argv]),exit_code=actual.returncode,output_sha256=corpus.digest(actual.stdout))
        return values
    def observe(command,path,unit=None,**kw):
        argv=['--json',*command.split('.'),str(path)]
        if unit is not None:argv+=['--logical-block-bytes',str(unit)]
        return launch(command+'-'+Path(path).name,argv,**kw)[0]
    def request(command,parameters,id='image:req',**extra):return dict(schema='org.disked.request/1',request_id=id,command=command,parameters=parameters,required_features=[],**extra)
    def encode(v):return json.dumps(v,ensure_ascii=False).encode()
    def field(value,path):
        for part in path.split('.'):value=value[int(part)] if isinstance(value,list) else value[part]
        return value
    def interpretation(value):return {k:v for k,v in value['result']['map'].items() if k!='capture'}
    def same_observation(a,b):
        assert a['status']==b['status'] and a['diagnostics']==b['diagnostics']
        if a['result'] is not None:
            assert interpretation(a)==interpretation(b)
            ac=a['result']['map']['capture'];bc=b['result']['map']['capture']
            for key in ['path','resolved_path','source_before','source_after','regions','region_manifest_sha256','regions_complete','observed_stable']:
                assert ac[key]==bc[key],(key,ac[key],bc[key])
    parent=args.root/'.aide-local';parent.mkdir(exist_ok=True)
    passed=False
    try:
        with tempfile.TemporaryDirectory(prefix='image-command-',dir=parent) as directory:
            directory=Path(directory);files=[]
            for case in corpus.recipes():
                path=directory/(case['name']+'.img');path.write_bytes(case['data']);files.append(path)
                # Exact expected findings are declared by independent fixture recipes.
                for command in ['image.inspect','table.verify']:
                    incomplete=case['name'] in {'mbr-truncated','gpt-short-backup'}
                    value=observe(command,path,code=4 if incomplete else 0,diagnostic='image_capture_incomplete' if incomplete else None)
                    assert value['result']['schema']=='org.disked.raw-image-observation/1'
                    assert value['result']['provider']=='provider.image.raw.prototype/1'
                    assert value['result']['scope']=='ordinary-local-raw-file'
                    map=value['result']['map'];capture=map['capture']
                    assert not capture['atomic_snapshot'] and not capture['whole_file_hashed']
                    assert capture['source_consistency']=='live-uncoordinated' and capture['path']==str(path)
                    if case['name']=='ebr-unavailable':
                        # This recipe declares 256 blocks for prefix-reader tests,
                        # but its raw file contains 40. The file profile derives
                        # geometry: its [10,210) root is outside [0,40), so no EBR
                        # walk is admitted. Do not reuse the prefix expectation.
                        assert map['geometry']['blocks']=='40' and map['mbr']['issues']==8 and map['walks']==[]
                    else:
                        for key,expected in case['checks'].items():assert field(map,key)==expected,(case['name'],key,field(map,key),expected)
                assert corpus.digest(path.read_bytes())==corpus.digest(case['data'])
            valid=directory/'gpt-valid.img';missing=directory/'missing.img';short=directory/'short.img';short.write_bytes(b'X')
            empty=directory/'empty.img';empty.write_bytes(b'')
            unicode=directory/'name-磁盘-🙂.img';unicode.write_bytes(corpus.gpt());files.extend([short,empty,unicode])
            before={p.name:corpus.digest(p.read_bytes()) for p in files}
            observe('image.inspect',empty)
            observe('table.verify',short,code=4,diagnostic='image_capture_incomplete')
            exact=observe('image.inspect',unicode);assert exact['result']['map']['capture']['path']==str(unicode)
            default=observe('table.verify',valid);explicit=observe('table.verify',valid,512);same_observation(default,explicit)
            unit=observe('image.inspect',valid,4096);assert unit['result']['map']['geometry']['logical_block_bytes']=='4096'
            literal=directory/'--help';literal.write_bytes(corpus.gpt());files.append(literal);before[literal.name]=corpus.digest(literal.read_bytes())
            launch('literal-path',['--json','image','inspect','--','--help'],cwd=directory)
            launch('option-placement',['--json','--logical-block-bytes','4096','table','verify',str(valid)])
            for argv,diagnostic in [(['image','inspect'],'missing_parameter'),(['table','verify'],'missing_parameter'),
                (['image','inspect',str(missing),'--logical-block-bytes','1024'],'invalid_option_value'),
                (['image','inspect',str(missing),'--logical-block-bytes','512','--logical-block-bytes','4096'],'duplicate_option'),
                (['image','inspect',str(missing),'--unknown'],'unknown_option')]:
                launch('parse-before-open-'+diagnostic,['--json',*argv],2,diagnostic,exe=args.fault,fault='OPEN_GUARD')
            for argv in [['--help'],['image','inspect','--help'],['table','verify','--help'],['build','inspect'],['commands']]:
                launch('essential-no-image-open',['--json',*argv],exe=args.fault,fault='OPEN_GUARD')
            for command in ['image.inspect','table.verify']:
                params=dict(path=str(valid),logical_block_bytes='512')
                wire=launch('stdio-'+command,['protocol','serve','--json'],data=encode(request(command,params)))[0]
                cli=observe(command,valid);same_observation(cli,wire)
                for patch,diagnostic in [({'expected_revision':'sha256:'+'0'*64},'unexpected_revision'),({'parameters':{}},'missing_parameter'),
                    ({'parameters':dict(path=str(missing),logical_block_bytes=512)},'invalid_parameter'),({'parameters':dict(path=str(missing),extra=True)},'unexpected_parameter')]:
                    value=request(command,params);value.update(patch)
                    launch('strict-before-open-'+diagnostic,['protocol','serve','--json'],2,diagnostic,exe=args.fault,data=encode(value),fault='OPEN_GUARD')
            refusal=observe('image.inspect',missing,code=3,diagnostic='image_source_open')
            assert refusal['diagnostics'][0]['platform_code']=='2'
            for fault,diagnostic in [('READ_ERROR','image_capture_incomplete'),('SHORT_READ','image_capture_incomplete'),('VERIFY_ERROR','image_capture_incomplete'),('CHANGED','image_source_changed'),('METADATA_CHANGED','image_source_changed')]:
                value=observe('table.verify',valid,exe=args.fault,fault=fault,code=4,diagnostic=diagnostic)
                assert value['status']=='failed' and value['result'] is not None
            observe('table.verify',valid,fault='READ_ERROR') # Ordinary product has no fault hook.
            for command,path in [('image.inspect',valid),('table.verify',valid),('table.verify',short),('image.inspect',missing)]:
                expected=observe(command,path,code=4 if path==short else 3 if path==missing else 0)
                g=Gui(args.exe,['--gui',*command.split('.'),str(path)],render=True)
                try:
                    assert not U.IsWindowEnabled(g.child(110));g.click(109);assert g.details()['reviewed'];g.click(110)
                    actual=wait(lambda:g.details() if 'status' in g.details() else None)
                    same_observation(expected,actual)
                    if args.evidence and command=='image.inspect' and path==valid:g.screenshot(args.evidence.parent/'image-inspection.png')
                    record('gui-'+command+'-'+path.name,response=actual,native=g.observation())
                finally:g.close()
                assert g.code==0 and g.output==b'' and g.error==b'' and g.created_files==[]
                for frontend in ['tui','shell']:
                    report=directory/'console-result.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                    process=subprocess.run([sys.executable,str(args.root/'tests/frontend/image_console_fixture.py'),str(args.exe),frontend,command,str(path),'512',str(report)],
                        cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=30)
                    actual=json.loads(report.read_text(encoding='utf-8'));assert process.returncode==0,actual
                    same_observation(expected,actual['response']);record(frontend+'-'+command+'-'+path.name,observation=actual);report.unlink()
            delayed=directory/'test-wait-valid.img';delayed.write_bytes(corpus.gpt());files.append(delayed);before[delayed.name]=corpus.digest(delayed.read_bytes())
            # A stdio timeout holds its single executing slot; no second wire
            # response is emitted for the late result. Essential commands survive.
            process=subprocess.Popen([str(args.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            lines=queue.Queue()
            def readlines():
                for line in process.stdout:lines.put(json.loads(line))
            reader=threading.Thread(target=readlines,daemon=True);reader.start()
            def send(v):process.stdin.write(encode(v)+b'\n');process.stdin.flush()
            try:
                started=time.monotonic();send(request('image.inspect',dict(path=str(delayed)),id='wait'))
                expired=lines.get(timeout=5);assert expired['status']=='unknown' and expired['operation_id'] is None
                assert expired['diagnostics'][0]['code']=='request_wait_expired' and time.monotonic()-started<5
                send(request('image.inspect',dict(path=str(missing)),id='busy'));busy=lines.get(timeout=1)
                assert busy['diagnostics'][0]['code']=='request_resource_limit'
                send(request('build.inspect',{},id='essential'));assert lines.get(timeout=1)['status']=='completed'
                time.sleep(1.8);assert lines.empty(),'Late unsolicited wire response'
                # Elapsed sleep is not evidence of callback quiescence. Observe
                # the slot's actual release with distinct read-only requests,
                # bounded by both time and the protocol's request quota.
                retries=[];end=time.monotonic()+8
                for attempt in range(40):
                    id='after:'+str(attempt);send(request('table.verify',dict(path=str(valid)),id=id));after=lines.get(timeout=2)
                    assert after['request_id']==id,after
                    retries.append(after)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit',after
                    assert time.monotonic()<end,after;time.sleep(.05)
                assert after['status']=='completed',retries
                process.stdin.close();assert process.wait(timeout=5)==6 and process.stderr.read()==b''
                record('stdio-wait-slot-late',expired=expired,busy=busy,after=after,release_observations=retries)
            finally:
                if process.poll() is None:process.kill();process.wait()
                reader.join(timeout=1);process.stdout.close();process.stderr.close()
            g=Gui(args.fault,['--gui','image','inspect',str(delayed)],render=True)
            try:
                g.click(109);g.click(110);assert g.details()['pending_request']=='gui:1';samples=[]
                for _ in range(3):
                    result=WP();started=time.monotonic();ok=U.SendMessageTimeoutW(g.window,0,0,0,2,250,C.byref(result))
                    samples.append(dict(responsive=bool(ok),elapsed_ms=(time.monotonic()-started)*1000))
                assert all(x['responsive'] and x['elapsed_ms']<250 for x in samples)
                g.set(201,str(missing));g.click(109);g.click(110);assert g.details()['diagnostics'][0]['code']=='request_resource_limit'
                g.click(104);g.choose(0);g.click(108);current=g.details();assert current['result']['target']['id']=='fake:alpha@1'
                late=wait(lambda:g.details() if 'earlier_request' in g.details() else None)
                assert late['request_id']==current['request_id'] and late['earlier_request']['request_id']=='gui:1'
                assert late['earlier_request']['status']=='completed';record('gui-image-late-isolated',samples=samples,late=late)
            finally:g.close()
            assert g.code==0 and g.created_files==[]
            assert before=={p.name:corpus.digest(p.read_bytes()) for p in files},'Source bytes changed'
            assert set(before)=={p.name for p in directory.iterdir()},'Unexpected output created'
        passed=True
    finally:
        if args.evidence:
            args.evidence.parent.mkdir(parents=True,exist_ok=True)
            args.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Shared image commands PASS '+str(len(records)),flush=True)

if __name__=='__main__':main()
