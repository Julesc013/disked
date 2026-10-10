"""Actual verification TUI/shell review in an owned hidden console."""
import json,sys
from pathlib import Path
from acquisition_console_fixture import run

FLAGS=('case-read','image-read','map-read','store-write','host-effects','private-metadata')
def command(p):
    if 'operation_id' in p:return ['operation','watch',p['operation_id'],'--state-dir',p['state_directory']]
    if p['phase']=='prepare':return ['image','verify','prepare',p['case_operation_id'],p['image'],'--map',p['map'],'--case-state-dir',p['case_directory'],'--state-dir',p['state_directory']]
    argv=['image','verify','execute','--definition-json',json.dumps(p['definition'],sort_keys=True,separators=(',',':'),ensure_ascii=False),'--definition-digest',p['definition_digest']]
    for flag in FLAGS:
        if p.get('allow_'+flag.replace('-','_')):argv.append('--allow-'+flag)
    return argv
if __name__=='__main__':
    report={};code=0
    try:
        p=json.loads(Path(sys.argv[2]).read_bytes());run(sys.argv[1],p,report,sys.argv[4],command(p))
    except Exception as e:report['fixture_error']=str(e);code=1
    Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
