"""Actual Windows process tests for DE-W012 synchronous CLI and stdio protocol."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import unittest


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def request(command='build.inspect',**changes):
    return dict(schema='org.disked.request/1',request_id='req:磁盘',command=command,parameters={},required_features=[],**changes)
def encode(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()


class NativeProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=read(ARGS.root/'spec/catalog/native-bootstrap.json')
        cls.commands=read(ARGS.root/'spec/catalog/commands.json')['commands']
        cls.identity=read(ARGS.identity)
        cls.schema_bundle=None
        if ARGS.validate_schemas:
            sys.path.insert(0,str(ARGS.root/'spec/tools'))
            import specctl
            cls.schema_bundle=specctl.Bundle(ARGS.root/'spec')

    def launch(self,argv,data=b''):
        with tempfile.TemporaryDirectory(prefix='disked-protocol-') as directory:
            env={key:os.environ[key] for key in ('SystemRoot','WINDIR') if key in os.environ}
            env.update(PATH=str(Path(os.environ['SystemRoot'])/'System32'),TEMP=directory,TMP=directory)
            process=subprocess.run([str(ARGS.exe),*argv],cwd=directory,env=env,input=data,capture_output=True,timeout=15)
            self.assertEqual([],list(Path(directory).iterdir()),'Application created files')
            self.assertNotEqual(97,process.returncode,'Provider initialization trap reached')
            self.assertNotIn(b'\x1b',process.stdout+process.stderr)
            return process

    def machine(self,argv,data=b'',exit_code=0):
        result=self.launch(argv,data)
        self.assertEqual(exit_code,result.returncode,result.stdout+result.stderr)
        self.assertEqual(b'',result.stderr)
        self.assertTrue(result.stdout.endswith(b'\n'))
        self.assertNotIn(b'\r',result.stdout)
        values=[json.loads(line) for line in result.stdout.splitlines()]
        for value in values:
            if self.schema_bundle:self.schema_bundle.validate('urn:disked:schema:response:1',value)
            self.assertEqual({'schema','request_id','status','operation_id','result','diagnostics','evidence'},set(value))
            self.assertEqual('org.disked.response/1',value['schema'])
            self.assertIsNone(value['operation_id'])
            for d in value['diagnostics']:
                self.assertEqual({'code','severity','message_key','parameters','platform_code','remediation'},set(d))
        return values

    def protocol(self,data,exit_code=0,ndjson=False):
        return self.machine(['protocol','serve','--format='+('ndjson' if ndjson else 'json')],data,exit_code)

    def test_build_identity_and_machine_aliases(self):
        expected=dict(self.identity['identity'],fake_provider=self.profile['fake_provider_id'],image_provider=self.profile['image_provider_id'],acquisition_provider=self.profile['acquisition_provider_id'],report_provider=self.profile['report_provider_id'],verification_provider=self.profile['verification_provider_id'])
        for argv in [['--json','build','inspect'],['build','--format','json','inspect'],['build','inspect','-j']]:
            value=self.machine(argv)[0]
            self.assertEqual(expected,value['result']);self.assertEqual('cli',value['request_id'])
        human=self.launch(['build','inspect'])
        self.assertEqual(expected,dict(line.split('=',1) for line in human.stdout.decode().splitlines()))
        self.assertEqual(0,human.returncode)

    def test_discovery_has_exact_registry_and_real_handler_subset(self):
        value=self.machine(['commands','--json'])[0]['result']['commands']
        self.assertEqual([c['id'] for c in self.commands],[c['id'] for c in value])
        self.assertEqual(set(self.profile['implemented_commands']),{c['id'] for c in value if c['availability']=='available'})
        for descriptor,actual in zip(self.commands,value):
            self.assertEqual(descriptor['aliases'],actual['aliases'])
            self.assertEqual('planned',actual['contract_status'])

    def test_help_every_spelling_and_operand_independence(self):
        for command in self.commands:
            for words in [command['words'],*(alias.split() for alias in command['aliases'])]:
                with self.subTest(words=words):
                    result=self.machine([*words,'--help','--json'])[0]['result']
                    self.assertEqual([command['id']],[c['id'] for c in result['commands']])
        for words in [[],['help'],['--help']]:
            self.assertEqual(len(self.commands),len(self.machine([*words,'--json'])[0]['result']['commands']))
        self.assertTrue(all(c['words'][0]=='partition' for c in self.machine(['help','part','--json'])[0]['result']['commands']))

    def test_errors_are_framed_after_complete_parse(self):
        for argv,code,exit_code in [(['build','inspect','--unknown'],'unknown_option',2),
                (['provider','resolve'],'command_unavailable',3),(['unknown'],'command_unavailable',3),
                (['build','inspect','extra'],'unexpected_operand',2),(['build','inspect','--gui'],'argument_conflict',2),
                (['build','inspect','--interactive=yes'],'argument_conflict',2),
                (['image','inspect','--','--help'],'image_source_open',3)]:
            # Place the format before literal-tail arguments where necessary.
            result=self.machine(['--json',*argv],exit_code=exit_code)[0]
            self.assertIn(code,[d['code'] for d in result['diagnostics']])
        self.assertEqual('unknown_option',self.machine(['build','inspect','--unknown','--json'],exit_code=2)[0]['diagnostics'][0]['code'])
        for argv in [['--json','--format=human'],['--format=human','--json']]:
            result=self.launch(['build','inspect',*argv]);self.assertEqual(2,result.returncode)
            self.assertEqual(b'',result.stdout);self.assertIn(b'argument_conflict',result.stderr)

    def test_unavailable_frontends_and_prompt_channels(self):
        # Explicit GUI is exercised by the native window suite; pipes do not
        # prohibit a separately requested GUI. TUI requires terminal channels.
        for argv,code in [(['--tui'],'frontend_unavailable'),
                         (['--cli','--interactive=yes'],'interaction_unavailable'),(['--interactive=yes'],'interaction_unavailable')]:
            result=self.launch(['build','inspect',*argv]);self.assertEqual(3,result.returncode)
            self.assertEqual(b'',result.stdout);self.assertIn(code.encode(),result.stderr)

    def test_strict_request_and_correlation(self):
        value=self.protocol(encode(request()))[0]
        self.assertEqual('req:磁盘',value['request_id']);self.assertEqual('completed',value['status'])
        for key in request():
            invalid=request();del invalid[key]
            self.assertEqual('@unparsed',self.protocol(encode(invalid),2)[0]['request_id'])
        for key,value in [('extra',1),('parameters',[]),('required_features',{}),('request_id',''),('request_id','a'*129),('request_id','a\0b')]:
            invalid=request();invalid[key]=value
            self.assertEqual('@unparsed',self.protocol(encode(invalid),2)[0]['request_id'])
        for key,value,code,status in [('required_features',['future'],'unsupported_feature',3),
                ('schema','org.disked.request/2','incompatible_schema',2),
                ('plan_digest','sha256:'+'0'*64,'unexpected_mutation_field',2),
                ('parameters',{'unexpected':True},'unexpected_parameter',2)]:
            invalid=request();invalid[key]=value
            result=self.protocol(encode(invalid),status)[0]
            self.assertEqual('req:磁盘',result['request_id']);self.assertEqual(code,result['diagnostics'][0]['code'])
        for command in ['protocol.serve','provider.resolve','unrecognized']:
            self.assertEqual('command_unavailable',self.protocol(encode(request(command)),3)[0]['diagnostics'][0]['code'])

    def test_malformed_json_and_encoding(self):
        for raw in [b'',b'[]',b'{}{}',b'{"a":1,"a":2}',b'{"a":1,"\\u0061":2}',b'{"x":1e999}',
                    b'\xef\xbb\xbf{}',b'\xff',b'"\\uD800"',b'{"x":NaN}',b'\x00']:
            with self.subTest(raw=raw):self.assertEqual('@unparsed',self.protocol(raw,2)[0]['request_id'])

    def test_ndjson_continues_refusals_and_preserves_order(self):
        a=request();a['request_id']='a'
        b=request('provider.resolve');b['request_id']='b'
        c=request();c['request_id']='c'
        values=self.protocol(encode(a)+b'\r\n{}\n'+encode(b)+b'\n'+encode(c),3,True)
        self.assertEqual(['a','@unparsed','b','c'],[v['request_id'] for v in values])
        self.assertEqual(['completed','refused','refused','completed'],[v['status'] for v in values])
        self.assertEqual('refused',self.protocol(b'\n',2,True)[0]['status'])

    def test_wire_byte_and_request_count_limits(self):
        raw=encode(request())
        self.assertEqual('completed',self.protocol(raw+b' '*(65536-len(raw)))[0]['status'])
        self.assertEqual('message_too_large',self.protocol(raw+b' '*(65537-len(raw)),2)[0]['diagnostics'][0]['code'])
        self.assertEqual('completed',self.protocol(raw+b' '*(65535-len(raw))+b'\n',ndjson=True)[0]['status'])
        self.assertEqual('message_too_large',self.protocol(raw+b' '*(65536-len(raw))+b'\n',2,True)[0]['diagnostics'][0]['code'])
        values=self.protocol((raw+b'\n')*257,2,True)
        self.assertEqual(257,len(values));self.assertEqual('request_limit',values[-1]['diagnostics'][0]['code'])
        self.assertTrue(all(v['status']=='completed' for v in values[:-1]))
        frame=raw+b' '*(65535-len(raw))+b'\n'
        values=self.protocol(frame*65,2,True)
        self.assertEqual(65,len(values));self.assertEqual('session_limit',values[-1]['diagnostics'][0]['code'])

    def test_resource_limits_end_stream(self):
        for raw,code in [(b'['*33+b']'*33,'depth_limit_exceeded'),(b'"'+b'a'*32769+b'"','string_limit_exceeded'),
                         (b'['+b'0,'*8191+b'0]','value_limit_exceeded')]:
            values=self.protocol(raw+b'\n'+encode(request())+b'\n',2,True)
            self.assertEqual(1,len(values));self.assertEqual(code,values[0]['diagnostics'][0]['code'])

    def test_stream_flushes_before_eof(self):
        process=subprocess.Popen([str(ARGS.exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        lines=queue.Queue()
        reader=threading.Thread(target=lambda:lines.put(process.stdout.readline()),daemon=True);reader.start()
        try:
            process.stdin.write(encode(request())+b'\n');process.stdin.flush()
            value=json.loads(lines.get(timeout=5));self.assertEqual('completed',value['status'])
            self.assertIsNone(process.poll(),'Server exited before EOF')
            process.stdin.close();self.assertEqual(0,process.wait(timeout=5))
            self.assertEqual(b'',process.stderr.read())
        finally:
            if process.poll() is None:process.kill();process.wait()
            process.stdout.close();process.stderr.close();reader.join(timeout=1)

    def test_ordinary_machine_command_does_not_read_pipeline_as_requests(self):
        value=self.machine(['build','inspect','--json'],b'malformed pipeline data')[0]
        self.assertEqual('completed',value['status'])

    def test_mode_inspection_uses_actual_host_in_cli_and_transport(self):
        cli=self.machine(['mode','explain','--json'])[0]['result']
        transport=self.protocol(encode(request('mode.explain')))[0]['result']
        for value in [cli,transport]:
            self.assertEqual('windows.standard-handles/1',value['observations']['adapter'])
            self.assertEqual('pipe',value['observations']['stdout']['kind'])
            self.assertEqual('machine-output',value['selection']['reason'])
            self.assertFalse(value['selection']['interactive'])
            self.assertTrue(value['policy_inputs']['tui_available'])

    def test_broken_output_is_failure(self):
        read_fd,write_fd=os.pipe();os.close(read_fd)
        try:
            result=subprocess.run([str(ARGS.exe),'build','inspect','--json'],stdin=subprocess.DEVNULL,stdout=write_fd,stderr=subprocess.PIPE,timeout=10)
        finally:os.close(write_fd)
        self.assertEqual(4,result.returncode);self.assertEqual(b'',result.stderr)

    def test_source_input_closure_and_pe_imports(self):
        expected={name:sha((ARGS.root/name).read_bytes()) for name in sorted(read(ARGS.root/'tools/build-inputs.json')['files'])}
        self.assertEqual(expected,self.identity['inputs'])
        self.assertEqual(sha(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()),self.identity['identity']['input_digest'])
        self.assertEqual(subprocess.check_output(['git','-C',str(ARGS.root),'rev-parse','HEAD'],text=True).strip(),self.identity['identity']['source_revision'])
        dumpbin=Path(self.identity['compiler_path']).with_name('dumpbin.exe')
        headers=subprocess.check_output([str(dumpbin),'/HEADERS',str(ARGS.exe)],text=True,timeout=15)
        for expected in ['8664 machine (x64)','magic # (PE32+)','10.00 subsystem version','subsystem (Windows CUI)','Dynamic base','NX compatible','Control Flow Guard']:
            self.assertIn(expected,headers)
        dependencies=subprocess.check_output([str(dumpbin),'/DEPENDENTS',str(ARGS.exe)],text=True,timeout=15)
        imported=re.findall(r'^\s+([A-Za-z0-9_.-]+\.dll)\s*$',dependencies,re.MULTILINE|re.IGNORECASE)
        self.assertEqual(['kernel32.dll'],sorted(s.lower() for s in imported))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--validate-schemas',action='store_true')
    for name in ('exe','root','identity'):parser.add_argument('--'+name,type=Path,required=True)
    ARGS=parser.parse_args();ARGS.exe=ARGS.exe.resolve();ARGS.root=ARGS.root.resolve()
    unittest.main(argv=[__file__],verbosity=2)
