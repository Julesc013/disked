"""Actual report TUI/shell review in a newly owned hidden console."""
import json,sys
from pathlib import Path
from acquisition_console_fixture import run

def command(p):
    if 'operation_id' in p:return ['operation','watch',p['operation_id'],'--state-dir',p['state_directory']]
    if p['phase']=='prepare':
        result=['evidence','export','prepare',p['case_operation_id'],p['destination'],'--case-state-dir',p['case_directory'],'--state-dir',p['state_directory']]
        if 'collection_path' in p:result+=['--collection',p['collection_path'],'--collection-digest',p['collection_digest']]
        for flag in ('identifiers','raw_values','interpretations','customer_data'):
            if p.get('include_'+flag):result.append('--include-'+flag.replace('_','-'))
        return result
    result=['evidence','export','execute','--definition-json',json.dumps(p['definition'],sort_keys=True,separators=(',',':'),ensure_ascii=False),'--definition-digest',p['definition_digest']]
    for flag in ('case-read','report-write','store-write','host-effects'):result.append('--allow-'+flag)
    if p.get('allow_collection_read'):result.append('--allow-collection-read')
    return result

if __name__=='__main__':
    report={};code=0
    try:
        p=json.loads(Path(sys.argv[2]).read_bytes());run(sys.argv[1],p,report,sys.argv[4],command(p))
    except Exception as error:report['fixture_error']=str(error);code=1
    Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
