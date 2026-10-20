"""Independent full-RGB verifier and scoped broker for the control-only preflight."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owned_pixel_boundary',HERE/'owned-window.py')
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
METHOD='owned-print-control/1'


def expected_rgb(challenge,phase):
    if type(challenge) is not bytes or len(challenge)!=16 or type(phase) is not int or phase not in (0,1):
        raise ValueError('Fixed challenge/phase required')
    colors=[hashlib.sha256(b'DiskEd pixel-origin/1\0'+challenge+bytes((phase,i))).digest()[:3] for i in range(16)]
    return b''.join(colors[(y//24)*4+x//60] for y in range(96) for x in range(240))


def rgb_pixels(body):
    if type(body) is not bytes or len(body)!=92160:raise ValueError('Fixed BGRA control payload required')
    value=bytearray(69120);value[0::3]=body[2::4];value[1::3]=body[1::4];value[2::3]=body[0::4]
    return bytes(value)


def png(rgb):
    def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
    rows=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(96))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,96,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows,9))+chunk(b'IEND',b'')


class Broker(boundary.Broker):
    method=METHOD

    def __init__(self,worker,fixtures,image,env,archive,*,expected_sha256):
        self.challenge=os.urandom(16);self.expected=[expected_rgb(self.challenge,p) for p in (0,1)]
        self.observations=[];self.archive=archive
        if self.expected[0]==self.expected[1] or any(value==bytes(69120) for value in self.expected):
            raise ValueError('Degenerate predeclared challenge')
        env['DISKED_PIXEL_CHALLENGE']=self.challenge.hex()
        super().__init__(worker,fixtures,image,env,expected_sha256=expected_sha256)

    def _read_pixels(self,value):
        phase=len(self.observations)
        if phase>=2:raise ValueError('Exactly two predeclared phases allowed')
        producer_env=dict(os.environ);producer_env.pop('DISKED_PIXEL_CHALLENGE',None)
        result=subprocess.run([sys.executable,'-B',str(HERE/'pixel-print.py'),str(value['window']),
                               str(value['pid']),value['desktop']],capture_output=True,timeout=10,env=producer_env)
        self.archive.writestr('pixel-origin/producer-'+str(phase)+'-stderr.log',result.stderr[:4096])
        if result.returncode or len(result.stdout)>96256 or len(result.stderr)>4096:
            self.observations.append(dict(phase=phase,producer_exit=result.returncode,exact_all_pixels=False))
            raise RuntimeError('Control print helper failed: '+result.stderr[-2048:].decode(errors='replace'))
        header,separator,body=result.stdout.partition(b'\n')
        if not separator or len(header)>4096:raise ValueError('Control envelope')
        observed=json.loads(header)
        if observed['method']!=METHOD or observed['sha256']!=hashlib.sha256(body).hexdigest():
            raise ValueError('Control producer transport differs')
        rgb=rgb_pixels(body);matched=rgb==self.expected[phase]
        row=dict(phase=phase,expected_rgb_sha256=hashlib.sha256(self.expected[phase]).hexdigest(),
                 actual_rgb_sha256=hashlib.sha256(rgb).hexdigest(),exact_all_pixels=matched,
                 observation=observed,execution_succeeded=observed['api_succeeded'] is True,
                 stale_other_phase_rejected=rgb!=self.expected[1-phase],
                 zero_surface_rejected=self.expected[phase]!=bytes(69120))
        self.observations.append(row)
        self.archive.writestr('pixel-origin/phase-'+str(phase)+'.bgra',body)
        self.archive.writestr('pixel-origin/phase-'+str(phase)+'.png',png(rgb))
        self.archive.writestr('pixel-origin/phase-'+str(phase)+'.json',json.dumps(row,sort_keys=True).encode())
        path=self.temp/('pixel-paint-'+str(phase)+'.json')
        if path.exists():
            handle=self.fixtures._open(path,0x80000080,share=1)
            try:
                form,tag=self.fixtures._form(handle)
                if (form.directory or form.links!=1 or not 0<form.size<=4096 or tag.attributes&0x400 or
                        self.fixtures._final(handle)!=path):raise ValueError('Paint diagnostic form')
                import msvcrt
                fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
                with os.fdopen(fd,'rb') as stream:data=stream.read(4097)
                if len(data)>4096:raise ValueError('Paint diagnostic bound')
                self.archive.writestr('pixel-origin/paint-'+str(phase)+'.json',data)
            finally:
                if handle:self.worker.k.CloseHandle(handle)
        if not matched or not row['execution_succeeded']:
            raise ValueError('Independent pixel-origin comparison failed for phase'+str(phase))
        return result.stdout

    def report(self):
        return dict(method=METHOD,scope='Control-only preflight;not product capture admission',
                    challenge=self.challenge.hex(),phases=self.observations,
                    passed=len(self.observations)==2 and all(r.get('exact_all_pixels') and
                        r.get('execution_succeeded') and r.get('stale_other_phase_rejected') and
                        r.get('zero_surface_rejected') for r in self.observations),
                    display_dc_read=False,desktop_switched=False,capture_qualified=False)
