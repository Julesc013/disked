import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'spec/tools'))
import specctl as sc
v=json.loads(Path(sys.argv[2]).read_bytes());b=sc.Bundle(root/'spec');count=0
for event in v['producer_events']:
    for kind,obj in [('acquisition-operation-event',event),('acquisition-worker-record',event['payload']['record']),
        ('acquisition-worker-state',event['payload']['record']['state'])]:
        b.validate(sc.SCHEMA_PREFIX+kind+':1',obj);count+=1
print(json.dumps(dict(passed=True,events=len(v['producer_events']),checks=count,scope='Producer conformance; independent native definition/coverage checks are separate.')))
