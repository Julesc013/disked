"""Independent full-RGB verifier and scoped broker for the control-only preflight."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time
import zlib

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owned_pixel_boundary',HERE/'owned-window.py')
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
METHOD='owned-print-control/1'


def producer_environment(env):
    value=dict(env);value.pop('DISKED_PIXEL_CHALLENGE',None)
    return value


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

    def __init__(self,worker,fixtures,image,env,archive,*,expected_sha256,retire_job,check):
        self.challenge=os.urandom(16);self.expected=[expected_rgb(self.challenge,p) for p in (0,1)]
        self.observations=[];self.archive=archive
        self.retire_job,self.check=retire_job,check;self.producer_job=None;self.producer_retirements=[]
        if self.expected[0]==self.expected[1] or any(value==bytes(69120) for value in self.expected):
            raise ValueError('Degenerate predeclared challenge')
        env['DISKED_PIXEL_CHALLENGE']=self.challenge.hex()
        super().__init__(worker,fixtures,image,env,expected_sha256=expected_sha256)
        self.producer_env=producer_environment(env)

    def _read_owned(self,path,limit):
        handle=self.fixtures._open(path,0x80000080,share=1)
        try:
            form,tag=self.fixtures._form(handle)
            if (form.directory or form.links!=1 or not 0<=form.size<=limit or tag.attributes&0x400 or
                    self.fixtures._final(handle)!=path or self.fixtures._identity(handle)[0]!=self.fixtures.volume):
                raise ValueError('Control diagnostic form')
            import msvcrt
            fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
            with os.fdopen(fd,'rb') as stream:body=stream.read(limit+1)
            if len(body)>limit:raise ValueError('Control diagnostic bound')
            return body
        finally:
            if handle:self.worker.k.CloseHandle(handle)

    def _producer(self,value,job):
        if job is None:raise ValueError('Owned job required for producer')
        self.check();self.producer_job=type(job)();child=None
        try:
            child=self.worker.launch([sys.executable,'-B',str(HERE/'pixel-print.py'),str(value['window']),
                                      str(value['pid']),value['desktop']],self.producer_env,self.producer_job,variant='basic-stdio')
            self.last_producer_pid=child.pid;log=self.worker.log_path;until=time.monotonic()+10
            while child.poll() is None:
                self.check()
                if time.monotonic()>until:raise TimeoutError('Owned control producer deadline')
                time.sleep(.2)
            code=child.wait(timeout=1)
        finally:
            try:self._retire_producer()
            finally:
                if child:child.close()
        body=self._read_owned(log,98304)
        self.last_producer_log=body
        warning=('Failed to find real location of '+sys.executable).encode()
        if body.startswith(warning):
            line,separator,body=body.partition(b'\n')
            if not separator or line.rstrip(b'\r')!=warning:raise ValueError('Unexpected Python startup prefix')
        if code:
            if body.startswith(b'Traceback') and len(body)<=4096:
                self.archive.writestr('pixel-origin/producer-'+str(len(self.observations))+'-stderr.log',body)
            raise RuntimeError('Ordinary print helper exited '+str(code))
        return body

    def _retire_producer(self):
        if self.producer_job is not None:
            self.producer_retirements.append(self.retire_job(self.producer_job))
            self.producer_job=None

    def finish(self,*,quiescent):
        self._retire_producer()
        return super().finish(quiescent=quiescent)

    def _read_pixels(self,value,job=None):
        phase=len(self.observations)
        if phase>=2:raise ValueError('Exactly two predeclared phases allowed')
        raw=self._producer(value,job)
        if len(raw)>96256:raise ValueError('Control producer output bound')
        header,separator,body=raw.partition(b'\n')
        if not separator or len(header)>4096:raise ValueError('Control envelope')
        observed=json.loads(header)
        token=observed['producer_identity']
        if (token['pid']!=self.last_producer_pid or token['user_sid']!=self.worker.user_sid or
                token['integrity_sid']!='S-1-16-8192' or not token['restricted'] or token['administrator'] or
                token['elevated'] or token['appcontainer']):raise ValueError('Producer ordinary token differs')
        if observed['method']!=METHOD or observed['sha256']!=hashlib.sha256(body).hexdigest():
            raise ValueError('Control producer transport differs')
        rgb=rgb_pixels(body);matched=rgb==self.expected[phase]
        known=rgb in self.expected or rgb==bytes(69120)
        row=dict(phase=phase,expected_rgb_sha256=hashlib.sha256(self.expected[phase]).hexdigest(),
                 actual_rgb_sha256=hashlib.sha256(rgb).hexdigest(),exact_all_pixels=matched,
                 observation=observed,producer_in_owned_job=True,execution_succeeded=observed['api_succeeded'] is True,
                 stale_other_phase_rejected=rgb!=self.expected[1-phase],
                 zero_surface_rejected=self.expected[phase]!=bytes(69120),pixels_retained=known)
        self.observations.append(row)
        # Unknown surfaces are hash-only evidence; do not retain unrelated pixels
        # through either the image artifacts or a producer's binary stdout log.
        if known:
            self.archive.writestr('pixel-origin/producer-'+str(phase)+'.log',getattr(self,'last_producer_log',raw))
            self.archive.writestr('pixel-origin/phase-'+str(phase)+'.bgra',body)
            self.archive.writestr('pixel-origin/phase-'+str(phase)+'.png',png(rgb))
        self.archive.writestr('pixel-origin/phase-'+str(phase)+'.json',json.dumps(row,sort_keys=True).encode())
        path=self.temp/('pixel-paint-'+str(phase)+'.json')
        if path.exists():
            self.archive.writestr('pixel-origin/paint-'+str(phase)+'.json',self._read_owned(path,4096))
        if not matched or not row['execution_succeeded']:
            raise ValueError('Independent pixel-origin comparison failed for phase'+str(phase))
        return raw

    def report(self):
        return dict(method=METHOD,scope='Control-only preflight;not product capture admission',
                    challenge=self.challenge.hex(),phases=self.observations,
                    passed=len(self.observations)==2 and all(r.get('exact_all_pixels') and
                        r.get('execution_succeeded') and r.get('stale_other_phase_rejected') and
                        r.get('zero_surface_rejected') for r in self.observations),
                    producer_profile='Same restricted actor,separate owned producer job in the same campaign',
                    producer_job_retirements=self.producer_retirements,
                    producer_jobs_retired=self.producer_job is None,
                    display_dc_read=False,desktop_switched=False,capture_qualified=False)
