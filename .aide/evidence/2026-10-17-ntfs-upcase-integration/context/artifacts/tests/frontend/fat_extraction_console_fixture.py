"""Reuse the owned acquisition console journey with an explicit extraction form."""
import json
from pathlib import Path
import sys
from acquisition_console_fixture import run

if __name__=='__main__':
    report={};code=0
    try:
        request=json.loads(Path(sys.argv[2]).read_bytes())
        run(sys.argv[1],request['parameters'],report,sys.argv[4],request['command'])
    except Exception as error:
        report['fixture_error']=str(error);code=1
    Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
