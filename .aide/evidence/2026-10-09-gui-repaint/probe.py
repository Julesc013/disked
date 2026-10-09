"""Inspect one owned private-desktop review; never submit or access case files."""
import ctypes as C,json,sys
from ctypes import wintypes as W
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R/'tests/frontend'))
from gui_fixture import Gui,U,bind
from report_console_fixture import command
E=R/'.aide-local/goal-0.1.0/export-repaint-5d88032';E.mkdir(exist_ok=False)
Q=R/'.aide/evidence/2026-10-09-product-export/reproduction-1f80711f'
sample=json.loads((Q/'product-export.json').read_bytes())['samples'][0]
definition=sample['definition'];parameters=dict(phase='execute',definition=definition,
    definition_digest=sample['header']['definition_digest'],allow_case_read=True,
    allow_report_write=True,allow_store_write=True,allow_host_effects=True)
product=R/'.aide-local/artifacts/DE-W034-product-export-1f80711f/disked.exe'
redraw=bind(U,'RedrawWindow',W.BOOL,[W.HWND,C.c_void_p,W.HANDLE,W.UINT])
ui=Gui(product,['--gui',*command(parameters)],render=True)
try:
    ui.click(109);review=ui.details();assert review['reviewed'] and review['command']=='evidence.export'
    caption=ui.text(110);assert caption=='&Submit reviewed' and U.IsWindowEnabled(ui.child(110))
    ui.screenshot(E/'before.png')
    assert redraw(ui.window,None,None,0x585)
    ui.screenshot(E/'after.png')
    assert ui.details()==review and ui.text(110)==caption
    observation=ui.observation()
finally:
    ui.close();assert ui.code==0 and not ui.error
result=dict(passed=True,scope='Owned GUI review/caption/repaint only; no submit, case access or report effect',
    caption=caption,review=review,observation=observation,executable=str(product),source_revision='1f80711f9bfe9d8a18a1cf92878f98a117c8f0d9')
(E/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('review','observation')}))
