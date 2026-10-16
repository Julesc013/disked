"""Retention/list/release journey in a hidden fixture-owned console."""
import json
from pathlib import Path
import sys
from image_console_fixture import run
from console_tui_fixture import key


def main():
    exe,frontend,path,root,output,options=sys.argv[1:7]
    report={};code=0
    registry=json.loads((Path(root)/'spec/catalog/commands.json').read_bytes())['commands']
    try:
        def followup(observed,wait,result):
            cid=observed['result']['capture_retention']['capture_id']
            previous=observed['request_id'];result['retention_journey']=[]
            def response(text,phase):
                compact=''.join(line.strip() for line in text.splitlines());decoder=json.JSONDecoder();found=None
                for at,char in enumerate(compact):
                    if char!='{':continue
                    try:value,_=decoder.raw_decode(compact[at:])
                    except ValueError:continue
                    if isinstance(value,dict) and value.get('schema')=='org.disked.response/1' and value.get('request_id')!=previous:
                        data=value.get('result')
                        if isinstance(data,dict) and data.get('scope')=='retained-fat-capture' and data.get('phase')==phase:found=value
                return found
            for command,phase in [('image.capture.inspect','list'),('image.capture.release','release')]:
                if frontend=='shell':
                    line=' '.join(command.split('.'))+(' --capture-id '+cid if phase=='release' else '')
                    for char in line:key(0,char)
                else:
                    key(0x71);index=next(i for i,v in enumerate(registry) if v['id']==command)
                    for _ in range(index):key(0x28)
                    key(13,'\r')
                    if phase=='release':
                        for char in cid:key(0,char)
                key(0x78);key(0x78)
                value=wait(lambda text:response(text,phase));assert value['status']=='completed',value
                if phase=='list':assert value['result']['captures'][0]['capture_id']==cid
                else:assert value['result']['released'] and value['result']['capture_id']==cid
                result['retention_journey'].append(value);previous=value['request_id']
        run(exe,frontend,'image.inspect',path,'-',report,json.loads(options),followup)
    except Exception as error:report['fixture_error']=str(error);code=1
    Path(output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)


if __name__=='__main__':main()
