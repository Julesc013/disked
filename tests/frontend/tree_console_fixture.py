"""Persistent tree session in a new fixture-owned hidden console."""
import json,re,sys
from pathlib import Path
from acquisition_console_fixture import run
from console_tui_fixture import key

def main():
    exe,request_path,output,frontend,root=sys.argv[1:6]
    request=json.loads(Path(request_path).read_bytes());report={};code=0
    registry=json.loads((Path(root)/'spec/catalog/commands.json').read_bytes())['commands']
    index=next(i for i,c in enumerate(registry) if c['id']=='filesystem.tree.inspect')
    try:
        def followup(opened,wait,result,observe):
            assert opened['status']=='completed'
            sid=opened['result']['session_id'];previous=opened['request_id'];result['tree_journey']=[]
            def find(text,phase):
                compact=''.join(line.strip() for line in text.splitlines());decoder=json.JSONDecoder();found=None
                for at,char in enumerate(compact):
                    if char!='{':continue
                    try:v,_=decoder.raw_decode(compact[at:])
                    except ValueError:continue
                    if isinstance(v,dict) and v.get('schema')=='org.disked.response/1' and v.get('request_id')!=previous:
                        body=v.get('result')
                        if isinstance(body,dict) and body.get('session_id')==sid and body.get('phase')==phase:found=v
                return found
            def execute(phase,fields=None):
                nonlocal previous
                def active(text):return text[max(text.rfind('DiskEd |'),text.rfind('DiskEd shell |')):]
                fields=dict(phase=phase,**(fields or {}),session_id=sid)
                if frontend=='shell':
                    line='filesystem tree '+' '.join('--'+k.replace('_','-')+' '+v for k,v in fields.items())
                    for char in line:key(0,char)
                else:
                    key(0x71)
                    wait(lambda text:'COMMAND EXPLORER' in active(text))
                    for _ in range(index):key(0x28)
                    wait(lambda text:'> filesystem.tree.inspect ' in active(text))
                    key(13,'\r');wait(lambda text:'TYPED FORM' in active(text))
                    # Edit by rendered field labels; do not assume field ordering.
                    for name,value in fields.items():
                        focused=re.compile(r'> ([a-z_]+) = "([^"\n]*)"')
                        for _ in range(20):
                            text=active(observe());match=re.search(r'> '+re.escape(name)+r' = "([^"\n]*)"',text)
                            if match:break
                            prior=focused.search(text)
                            assert prior,('missing focused field',text)
                            prior_name=prior.group(1)
                            key(9,'\t')
                            wait(lambda t:(m:=focused.search(active(t))) and m.group(1)!=prior_name)
                        assert match,(name,text)
                        for _ in range(len(match.group(1))):key(8,'\b')
                        for char in value:key(0,char)
                        wait(lambda t:re.search(r'> '+re.escape(name)+r' = '+re.escape(json.dumps(value)),active(t)))
                key(0x78)
                wait(lambda text:('F9 submits:' in active(text)) if frontend=='shell' else ('REQUEST REVIEW' in active(text)))
                key(0x78)
                value=wait(lambda text:find(text,phase));assert value['status']=='completed',value
                previous=value['request_id'];result['tree_journey'].append(value)
                return value['result']
            for _ in range(5):
                page=execute('next')
                if 'page' in page:break
            assert 'page' in page and int(page['page']['sequence'])==1
            chunk=execute('read',dict(page_sequence='1',byte_offset='0',byte_count='64'))
            assert chunk['returned_bytes']=='64' and len(chunk['data'])==128
            assert execute('cancel')['cancellation_requested']
            for _ in range(5):
                closed=execute('close')
                if closed['state']=='closed':break
            assert closed['state']=='closed' and closed['worker']['worker']['observation']=='exited'
        run(exe,request['parameters'],report,frontend,request['command'],followup)
    except Exception as e:report['fixture_error']=str(e);code=1
    Path(output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return code

if __name__=='__main__':raise SystemExit(main())
