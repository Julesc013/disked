"""Check nonzero/conflicting FAT selection using the already qualified binary."""
import argparse,hashlib,importlib.util,json,struct,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--fixture-root',type=Path,required=True);p.add_argument('--probe',type=Path,required=True)
p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=a.fixture_root.resolve();probe=a.probe.resolve();summary=json.loads(a.summary.read_bytes())
assert summary['passed'] and summary['source_revision']=='b770b3feecb92532c6cc884ec2ea5dbb0455a1f9'
expected=next(r for r in summary['artifacts'] if r['kind']=='fat_traversal_probe')['sha256']
assert 'sha256:'+hashlib.sha256(probe.read_bytes()).hexdigest()==expected
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==summary['source_revision']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
sys.path.insert(0,str(root/'tests/images'))
spec=importlib.util.spec_from_file_location('qualified_traversal_fixture',root/'tests/images/test_fat_traversal.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
rows=[]
for bits,selected in ((12,1),(16,1),(32,1),(32,0)):
 tree=fixture.Tree(bits);tree.chain([10,12]);tree.directory([fixture.short(name=b'DIR        ',attributes=16,cluster=10)])
 tree.directory(fixture.files(20),parent='entry:'+str(tree.root),clusters=[10,12])
 if bits==32:
  boot=bytearray(tree.boot);struct.pack_into('<H',boot,40,0x81);tree.regions[0]=bytes(boot)
 request=tree.request();request['copy']=str(selected)
 table0=tree.offset+tree.g['reserved']*tree.unit
 for region in request['regions']:
  if int(region['offset'])==table0:region['hex']='00'*len(bytes.fromhex(region['hex']))
 data=json.dumps(request,separators=(',',':')).encode()+b'\n'
 r=subprocess.run([str(probe)],input=data,capture_output=True,timeout=30);assert r.returncode==0 and not r.stderr
 result=json.loads(r.stdout);pages=result['pages'];events=[e for page in pages for e in page['events']]
 previous=None
 for n,page in enumerate(pages,1):
  body=dict(page);digest=body.pop('page_digest');assert page['sequence']==str(n) and page['previous_page_digest']==previous
  assert digest=='sha256:'+hashlib.sha256(b'disked:fat-traversal-page:1\n'+json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  previous=digest;assert page['binding']['fat_copy']==str(selected)
 volume=next(e for e in events if e['type']=='volume')
 assert volume['active_copy_selected']==(bits!=32 or selected==1)
 for event in events:
  if event['type']=='allocation':assert table0+selected*tree.table<=int(event['source_offset'])<table0+(selected+1)*tree.table
 if selected==1:
  assert pages[-1]['status']=='complete';fixture.check_metadata(tree,events)
  assert sum(e['type']=='record' for e in events)==21
 else:assert pages[-1]['status']=='partial' and any(e['type']=='directory_end' and e['chain']=='free' for e in events)
 rows.append(dict(bits=bits,selected_copy=selected,status=pages[-1]['status'],entries=sum(e['type']=='record' for e in events),
                  input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(r.stdout).hexdigest()))
a.output.write_text(json.dumps(dict(passed=True,source_revision=summary['source_revision'],probe_sha256=expected,cases=4,records=rows,
 scope='Supplemental oracle over the exact qualified binary and frozen fixtures; no native source or tests changed.'),indent=2)+'\n',encoding='utf-8',newline='\n')
print('PASS four conflicting/nonzero FAT copy cases against the qualified binary.')
