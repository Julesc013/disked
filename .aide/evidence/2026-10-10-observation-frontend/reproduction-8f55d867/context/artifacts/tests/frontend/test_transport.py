"""Read-only fake graph via product argv/stdin and the direct service probe."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def request(command,parameters=None,**fields):
    return dict(schema='org.disked.request/1',request_id='probe',command=command,parameters=parameters or {},required_features=[],**fields)
def encode(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=None
        if ARGS.validate_schemas:
            sys.path.insert(0,str(ARGS.root/'spec/tools'))
            import specctl
            cls.bundle=specctl.Bundle(ARGS.root/'spec')

    def launch(self,args,data=b'',code=0,guard=False):
        with tempfile.TemporaryDirectory(prefix='disked-fake-') as directory:
            env={k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ}
            env.update(PATH=str(Path(os.environ['SystemRoot'])/'System32'),TEMP=directory,TMP=directory)
            p=subprocess.run([str(ARGS.guard if guard else ARGS.exe),*args],input=data,capture_output=True,cwd=directory,env=env,timeout=10)
            self.assertEqual([],list(Path(directory).iterdir()));self.assertEqual(code,p.returncode,p.stdout+p.stderr)
            self.assertEqual(b'',p.stderr)
            return p.stdout

    def response(self,args,data=b'',code=0,guard=False):
        v=json.loads(self.launch(args,data,code,guard))
        if self.bundle:self.bundle.validate('urn:disked:schema:response:1',v)
        return v

    def test_direct_argv_and_transport_share_results(self):
        cases=[('target.list',['target','list'],{}),('topology.show',['topology','show'],{}),
               ('target.inspect',['show','fake:alpha@1'],dict(target_id='fake:alpha@1')),
               ('target.inspect',['show','fake:denied@1'],dict(target_id='fake:denied@1')),
               ('capability.explain',['capability','explain','fake:stale@1','partition.resize.plan'],dict(target_id='fake:stale@1',operation='partition.resize.plan'))]
        for command,argv,parameters in cases:
            direct=subprocess.run([str(ARGS.probe)],input=encode(dict(op='dispatch',command=command,parameters=parameters,revision=''))+b'\n',capture_output=True,timeout=10)
            self.assertEqual(0,direct.returncode);self.assertEqual(b'',direct.stderr)
            expected=json.loads(direct.stdout)
            cli=self.response([*argv,'--json']);cli['request_id']='probe'
            wire=self.response(['protocol','serve','--json'],encode(request(command,parameters)))
            self.assertEqual(expected,cli);self.assertEqual(expected,wire)
            result=wire['result']
            if self.bundle:
                if command=='target.list':self.bundle.validate('urn:disked:schema:fake-graph:1',result['graph'])
                if command=='topology.show':self.bundle.validate('urn:disked:schema:fake-graph:1',result)
                if command=='capability.explain':self.bundle.validate('urn:disked:schema:capability-assessment:1',result['assessment'])

    def test_revisions_refusals_and_ndjson_session_continue(self):
        graph=self.response(['topology','show','--json'])['result'];revision=graph['revision']
        commands=[('target.list',{}),('topology.show',{}),('target.inspect',dict(target_id='fake:alpha@1')),
                  ('capability.explain',dict(target_id='fake:alpha@1',operation='target.inspect'))]
        records=[]
        for command,parameters in commands:
            records.extend([request(command,parameters,expected_revision='sha256:'+'0'*64),request(command,parameters,expected_revision=revision)])
        records+=[request('target.inspect',dict(target_id='fake:removed@1')),request('capability.explain',dict(target_id='fake:alpha@1',operation='invented'))]
        output=self.launch(['protocol','serve','--format=ndjson'],b'\n'.join(encode(r) for r in records),3)
        values=[json.loads(line) for line in output.splitlines()]
        self.assertEqual(10,len(values))
        for i,v in enumerate(values[:8]):
            if i%2:self.assertEqual('completed',v['status'])
            else:self.assertEqual('revision_conflict',v['diagnostics'][0]['code'])
        self.assertEqual('target_not_found',values[8]['diagnostics'][0]['code'])
        self.assertEqual('operation_unavailable',values[9]['diagnostics'][0]['code'])

    def test_direct_and_transport_refusals_match(self):
        cases=[('target.inspect',dict(target_id='missing'),''),('target.list',{},'sha256:'+'0'*64),
               ('capability.explain',dict(target_id='fake:alpha@1',operation='invented'),''),('target.inspect',{},'')]
        for command,parameters,revision in cases:
            probe=dict(op='dispatch',command=command,parameters=parameters,revision=revision)
            process=subprocess.run([str(ARGS.probe)],input=encode(probe)+b'\n',capture_output=True,timeout=10)
            self.assertEqual(0,process.returncode);direct=json.loads(process.stdout)
            fields={'expected_revision':revision} if revision else {}
            exit_code=3 if direct['diagnostics'][0]['code']=='operation_unavailable' else 2
            wire=self.response(['protocol','serve','--json'],encode(request(command,parameters,**fields)),exit_code)
            self.assertEqual(direct,wire)

    def test_bad_arguments_and_envelopes_do_not_initialize_provider(self):
        for argv in [['target','inspect'],['topology','show','extra'],['capability','explain','fake:alpha@1'],['target','list','--unknown']]:
            self.response([*argv,'--json'],code=2,guard=True)
        for value in [request('target.inspect'),request('target.list',extra='bad'),request('target.list',expected_revision='bad'),
                      request('target.list',plan_digest='sha256:'+'0'*64),request('target.list',idempotency_key='x')]:
            self.response(['protocol','serve','--json'],encode(value),2,True)
        # The trap is active for an actual graph request, not merely compiled out.
        self.launch(['target','list','--json'],code=97,guard=True)

    def test_unknown_targets_not_resolved_by_alias_or_row_and_no_mutation(self):
        for target in ['0','fake:serial/CLONED','fake:path/A/0','fake:alpha@2','\\\\.\\PhysicalDrive0']:
            result=self.response(['target','inspect',target,'--json'],code=2)
            self.assertEqual('target_not_found',result['diagnostics'][0]['code'])
        result=self.response(['partition','resize','fake:alpha@1','--length=1GiB','--json'],code=3)
        self.assertEqual('command_unavailable',result['diagnostics'][0]['code'])

    def test_terminal_view_is_lossless_ascii_and_machine_preserves_utf8(self):
        for argv in [['target','list'],['topology','show'],['target','inspect','fake:volume@1']]:
            human=self.launch(argv);machine=self.response([*argv,'--json'])['result']
            self.assertTrue(all(b==10 or 32<=b<127 for b in human));self.assertEqual(machine,json.loads(human))
        target=self.response(['target','inspect','fake:volume@1','--json'])['result']['target']
        self.assertEqual('Label\x1b[31m\n\x7f\x9b\u202e磁盘💾',target['properties']['label'])
        for alias in [['list'],['ls'],['list','targets']]:
            self.assertEqual(7,len(self.response([*alias,'--json'])['result']['target_ids']))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['exe','guard','probe','root']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--validate-schemas',action='store_true');ARGS=p.parse_args()
    for name in ['exe','guard','probe','root']:setattr(ARGS,name,getattr(ARGS,name).resolve())
    unittest.main(argv=[__file__],verbosity=2)
