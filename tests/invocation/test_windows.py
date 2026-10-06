"""Real Windows launches; all writable files and consoles belong to the test."""
import argparse
import ctypes
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import _winapi

LAUNCHES=[]

def raw_launch(exe,argv,input_kind='absent',output_kind='file',error_kind='file'):
    with tempfile.TemporaryDirectory(prefix='disked-handles-') as directory:
        root=Path(directory)
        handles={};files=[];process=None
        try:
            for key,kind in [('stdin',input_kind),('stdout',output_kind),('stderr',error_kind)]:
                if kind=='absent':handles[key]=0
                elif kind=='invalid':handles[key]=0x12345678
                elif kind=='invalid_sentinel':handles[key]=ctypes.c_void_p(-1).value
                else:
                    path=root/(key+'.bin');f=path.open('w+b');files.append(f)
                    handle=msvcrt.get_osfhandle(f.fileno());os.set_handle_inheritable(handle,True);handles[key]=handle
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESTDHANDLES|subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow=0
            startup.hStdInput=handles['stdin'];startup.hStdOutput=handles['stdout'];startup.hStdError=handles['stderr']
            process,thread,pid,tid=_winapi.CreateProcess(str(exe),subprocess.list2cmdline([str(exe),*argv]),
                None,None,True,subprocess.DETACHED_PROCESS,None,directory,startup)
            _winapi.CloseHandle(thread)
            if _winapi.WaitForSingleObject(process,10000)!=0:
                _winapi.TerminateProcess(process,99);_winapi.WaitForSingleObject(process,5000);raise RuntimeError('Test child timeout')
            code=_winapi.GetExitCodeProcess(process)
            for f in files:f.close()
            out=(root/'stdout.bin').read_bytes() if output_kind=='file' else b''
            err=(root/'stderr.bin').read_bytes() if error_kind=='file' else b''
            expected={key+'.bin' for key,kind in [('stdin',input_kind),('stdout',output_kind),('stderr',error_kind)] if kind=='file'}
            if {p.name for p in root.iterdir()}!=expected:raise AssertionError('Unexpected application-created file')
            LAUNCHES.append(dict(kind='raw_standard_handles',argv=argv,stdin=input_kind,stdout=output_kind,stderr=error_kind,exit=code,
                                 stdout_bytes=len(out),stderr_bytes=len(err)))
            return code,out,err
        finally:
            for f in files:
                if not f.closed:f.close()
            if process is not None:_winapi.CloseHandle(process)


class WindowsInvocation(unittest.TestCase):
    def test_standard_handle_absence_and_invalidity(self):
        for kind in ['absent','invalid','invalid_sentinel','file']:
            code,out,err=raw_launch(ARGS.exe,['mode','explain','--json'],kind)
            self.assertEqual(0,code,(kind,out,err));self.assertEqual(b'',err)
            value=json.loads(out)['result'];actual=value['observations']['stdin']['kind']
            self.assertEqual('invalid' if kind in ('invalid','invalid_sentinel') else kind,actual)
            self.assertEqual('file',value['observations']['stdout']['kind'])
            self.assertEqual('machine-output',value['selection']['reason'])
            self.assertFalse(value['policy_inputs']['prompt_channel'])
        for kind in ['absent','invalid','invalid_sentinel']:
            code,out,err=raw_launch(ARGS.exe,['build','inspect','--json'],output_kind=kind)
            self.assertEqual(4,code,(kind,err));self.assertEqual(b'',out)

    def test_missing_stderr_and_transport_input(self):
        code,out,err=raw_launch(ARGS.exe,['build','inspect','--json'],error_kind='absent')
        self.assertEqual(0,code);self.assertEqual('completed',json.loads(out)['status'])
        code,out,err=raw_launch(ARGS.exe,['protocol','serve','--json'])
        self.assertEqual(4,code);self.assertEqual('input_error',json.loads(out)['diagnostics'][0]['code'])
        code,out,err=raw_launch(ARGS.exe,['--invalid'],error_kind='absent')
        self.assertEqual(4,code);self.assertEqual(b'',out)
        code,out,err=raw_launch(ARGS.exe,[],output_kind='absent',error_kind='absent')
        self.assertEqual(4,code)

    def test_pipe_observations_and_utf16_errors(self):
        result=subprocess.run([str(ARGS.exe),'mode','explain','--json'],input=b'',capture_output=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)
        value=json.loads(result.stdout)['result']
        for key in ['stdin','stdout','stderr']:self.assertEqual('pipe',value['observations'][key]['kind'])
        self.assertEqual('redirected-stream',value['bare_selection']['reason'])
        for argv in [['build','inspect','\ud800','--json'],['--format','\udfff','build','inspect','--json']]:
            result=subprocess.run([str(ARGS.exe),*argv],input=b'',capture_output=True,timeout=10)
            self.assertEqual(2,result.returncode,result.stderr);self.assertEqual(b'',result.stderr)
            self.assertIn('invalid_argument_encoding',[d['code'] for d in json.loads(result.stdout)['diagnostics']])

    def test_cmd_and_powershell_actual_launches(self):
        # Shell syntax is constant except the quoted test executable path.
        path=str(ARGS.exe)
        if any(c in path+os.environ['COMSPEC'] for c in '%!"\r\n'):raise RuntimeError('Shell test path contains unsupported quoting characters')
        shells=[('cmd','"'+os.environ['COMSPEC']+'" /d /s /c ""'+path+'" mode explain --json"'),
                ('powershell',['powershell.exe','-NoProfile','-NonInteractive','-Command',"& '"+path.replace("'","''")+"' mode explain --json; exit $LASTEXITCODE"]),
                ('pwsh',['pwsh','-NoProfile','-NonInteractive','-Command',"& '"+path.replace("'","''")+"' mode explain --json; exit $LASTEXITCODE"])]
        for shell,argv in shells:
            with tempfile.TemporaryDirectory(prefix='disked-shell-') as directory:
                result=subprocess.run(argv,cwd=directory,input=b'',capture_output=True,timeout=20)
                self.assertEqual(0,result.returncode,(shell,result.stderr));self.assertEqual(b'',result.stderr)
                value=json.loads(result.stdout)['result']
                self.assertEqual('machine-output',value['selection']['reason'])
                self.assertEqual([],list(Path(directory).iterdir()))
                LAUNCHES.append(dict(kind=shell,exit=result.returncode,observations=value['observations'],selection=value['selection']))

    def test_inherited_console_preserves_caller_state(self):
        for flags in [['--json'],['--cli','--interactive=yes'],['--interactive=yes'],['--json','--fixture-wrong-input']]:
            with self.subTest(flags=flags):self.console_case(flags)

    def console_case(self,flags):
        with tempfile.TemporaryDirectory(prefix='disked-console-') as directory:
            report=Path(directory)/'report.json'
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            result=subprocess.run([sys.executable,str(ARGS.root/'tests/invocation/console_fixture.py'),str(ARGS.exe),str(report),*flags],
                creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=20,cwd=directory)
            self.assertEqual(0,result.returncode,report.read_text(encoding='utf-8') if report.exists() else 'Missing fixture report')
            value=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(0,value['child_exit']);self.assertEqual(value['before'],value['after'])
            payload=json.loads(value['output'].strip());observation=payload.get('result',payload)
            self.assertEqual('console',observation['observations']['stdin']['kind'])
            self.assertEqual('console',observation['observations']['stdout']['kind'])
            self.assertEqual('shared-protected',observation['observations']['console_ownership'])
            if '--fixture-wrong-input' in flags:
                self.assertFalse(observation['observations']['console_input_verified'])
                self.assertFalse(observation['policy_inputs']['prompt_channel'])
                self.assertEqual('no-interactive-host',observation['bare_selection']['reason'])
            else:
                self.assertTrue(observation['observations']['console_input_verified'])
                self.assertEqual('interactive-terminal',observation['bare_selection']['reason'])
            self.assertEqual('--interactive=yes' in flags,observation['selection']['interactive'])
            self.assertEqual(['report.json'],[p.name for p in Path(directory).iterdir()])
            LAUNCHES.append(dict(kind='hidden_test_console_with_inherited_child',flags=flags,**value))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--evidence',type=Path)
    ARGS=parser.parse_args();ARGS.exe=ARGS.exe.resolve();ARGS.root=ARGS.root.resolve()
    result=unittest.main(argv=[__file__],verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(LAUNCHES,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
