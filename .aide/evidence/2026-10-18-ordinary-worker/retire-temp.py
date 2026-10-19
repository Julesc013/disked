"""Retire this worker's own temporary fixtures after its test job has exited."""
import importlib.util
import json
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parent
target=Path(sys.argv[1]).absolute()
work=Path(os.environ['DISKED_WORK_ROOT']).resolve()
if target!=Path(os.environ['TEMP']).absolute() or target.parent!=work/'native-x64' or target.name!='temp':
    raise ValueError('Cleanup target differs from this exact ordinary worker')
definition=importlib.util.spec_from_file_location('owned_workspace',root/'source/tools/workspace.py')
workspace=importlib.util.module_from_spec(definition);definition.loader.exec_module(workspace)
definition=importlib.util.spec_from_file_location('retirement_identity',root/'target.py')
observer=importlib.util.module_from_spec(definition);definition.loader.exec_module(observer)
token=observer.identity()
if token['administrator'] or token['elevated'] or token['appcontainer'] or not token['restricted'] or token['integrity_sid']!='S-1-16-8192':
    raise PermissionError('Ordinary restricted Medium fixture owner required')
size=workspace.tree_bytes(target,allocated=True,file_limit=20000,allow_links=True)
workspace.remove_owned_work(target,target.parent,'temp')
target.mkdir(mode=0o777)
if list(target.iterdir()):raise ValueError('Temporary root was not emptied')
print(json.dumps(dict(allocated_bytes_removed=size,root_recreated_empty=True,actual_token=token)))
