"""Native interrupted-owned-image restoration; independent whole-byte oracles."""
import argparse,contextlib,copy,hashlib,json,os,queue,shutil,struct,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_gpt_execution import canonical,sha,expected,receipts,fixture,change_array

def request(case,source='primary',phase='create',**extra):
    v=dict(phase=phase,image_hex=case['raw'].hex(),logical_block_bytes=case['capture']['block_bytes'],authoritative_copy=source,expected_capture_digest=case['definition']['capture_digest'],expected_plan_digest=case['plan_digest']);v.update(extra);return v
class Replies:
    """Drain both pipes; preserve diagnostics without extending reply deadlines."""

    def __init__(self, process):
        self.process = process
        self.rows = queue.Queue()
        self.error = None
        self.frames = 0
        self.last_phase = None
        self.stderr_tail = b''
        self.stderr_bytes = 0
        self.started = time.monotonic()
        self.out_thread = threading.Thread(target=self.read, daemon=True)
        self.err_thread = threading.Thread(target=self.read_errors, daemon=True)
        self.out_thread.start()
        self.err_thread.start()

    def read(self):
        try:
            for line in self.process.stdout:
                value = json.loads(line)
                self.frames += 1
                self.last_phase = value.get('phase') if isinstance(value, dict) else None
                self.rows.put(value)
        except Exception as error:
            self.error = repr(error)
        finally:
            self.rows.put(None)

    def read_errors(self):
        try:
            while block := self.process.stderr.read1(4096):
                self.stderr_bytes += len(block)
                self.stderr_tail = (self.stderr_tail + block)[-1048576:]
        except Exception as error:
            self.error = repr(error)

    def snapshot(self, phase):
        return dict(phase=phase, pid=self.process.pid, exit_code=self.process.poll(),
            elapsed_seconds=round(time.monotonic() - self.started, 3),
            frames=self.frames, last_reply_phase=self.last_phase, reader_error=self.error,
            stdout_reader_alive=self.out_thread.is_alive(),
            stderr_reader_alive=self.err_thread.is_alive(), stderr_bytes=self.stderr_bytes,
            stderr_tail=self.stderr_tail.decode('utf8', errors='backslashreplace'))

    def get(self, timeout=15, phase='reply'):
        try:
            return self.rows.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError(json.dumps(self.snapshot(phase), sort_keys=True)) from error

    def wait(self, timeout=15, phase='exit'):
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(json.dumps(self.snapshot(phase), sort_keys=True)) from error

    def join(self):
        self.out_thread.join(timeout=1)
        self.err_thread.join(timeout=1)

    def assert_drained(self, trace=False):
        self.join()
        assert not self.out_thread.is_alive() and not self.err_thread.is_alive(), self.snapshot('pipe-retirement')
        assert self.error is None, self.snapshot('reader-error')
        if trace:
            assert self.stderr_bytes == len(self.stderr_tail), 'Diagnostic trace exceeded retained bound'
            assert all(line.startswith(b'GPT_FIXTURE ') for line in self.stderr_tail.splitlines()), self.snapshot('unexpected-stderr')
        else:
            assert not self.stderr_bytes, self.snapshot('unexpected-stderr')

    def empty(self):
        return self.rows.empty()

    def get_nowait(self):
        return self.rows.get_nowait()


def send(process, value):
    process.stdin.write(canonical(value) + b'\n')
    process.stdin.flush()


def close(process, replies, observations):
    original_error = sys.exc_info()[1]
    kill_requested = False
    kill_error = None
    if process.poll() is None:
        try:
            process.kill()
            kill_requested = True
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            kill_error = repr(error)
    confirmed = process.poll() is not None
    if confirmed:
        replies.join()
        if not process.stdin.closed:
            process.stdin.close()
        if not replies.out_thread.is_alive():
            process.stdout.close()
        if not replies.err_thread.is_alive():
            process.stderr.close()
    observation = replies.snapshot('retirement')
    observation.update(kill_requested=kill_requested, kill_error=kill_error, exit_confirmed=confirmed)
    observations.append(observation)
    if not confirmed:
        print('UNCONFIRMED_RETIREMENT ' + json.dumps(observation, sort_keys=True), file=sys.stderr, flush=True)
        if original_error is not None:
            original_error.add_note('Fixture dependencies retained; process exit unconfirmed: ' + json.dumps(observation, sort_keys=True))
        else:
            raise TimeoutError('Fixture process exit unconfirmed: ' + json.dumps(observation, sort_keys=True))


@contextlib.contextmanager
def fixture_parent(root, state, observations):
    parent = (root / '.aide-local').resolve()
    parent.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='gpt-restore-', dir=parent)).resolve()
    assert directory.is_relative_to(parent) and directory != parent
    state['directory'] = str(directory)
    try:
        yield directory
        assert all(row['exit_confirmed'] for row in observations), 'Cleanup requires confirmed process exit'
        shutil.rmtree(directory)
        state['retained'] = False
    except BaseException as error:
        state.update(retained=True, error=repr(error))
        print('RETAINED_FIXTURE ' + str(directory), file=sys.stderr, flush=True)
        raise


def recovery_receipts(prepared):
    d=prepared['definition'];review=dict(schema='org.disked.gpt-restoration-review/1',restoration_digest=prepared['restoration_digest'],observed_image_digest=d['observed_image_digest'],reviewed=True,issuer='fixture-controller',evidence_digest=sha(b'independent-restoration-byte-oracle'))
    grant=dict(schema='org.disked.gpt-restoration-grant/1',restoration_digest=prepared['restoration_digest'],review_digest=sha(canonical(review)),original_manifest_digest=d['original_manifest_digest'],executor_digest=d['resources']['executor_digest'],patch_ids=[p['id'] for p in d['patches']],allow_fixture_restoration=True,allow_new_recovery_journal=True,acknowledge_nonatomic_same_volume=True);return review,grant
def expected_patches(case,current):
    out=[]
    for p in reversed(case['patches']):
        before=current[p['offset']:p['offset']+len(p['before'])]
        if before!=p['before']:out.append(dict(id=p['id'],offset=str(p['offset']),bytes=str(len(before)),before_sha256=sha(before),after_sha256=sha(p['before']),depends_on=[] if not out else [out[-1]['id']]))
    return out
def journal(raw,definition,digest,review,grant,store):
    if len(raw)<192:return 0
    assert raw[:8]==b'DEJPR001' and raw[160:192]==hashlib.sha256(raw[:160]).digest() and raw[40:72]==bytes.fromhex(digest[7:]) and raw[24:40]==bytes.fromhex(store['identity'][7:])[:16]
    assert raw[72:104]==hashlib.sha256(canonical(dict(original=definition['resources'],recovery_store=store))).digest() and raw[104:136]==hashlib.sha256(canonical(dict(provider=definition['resources']['provider_id'],executor=store['executor_digest']))).digest()
    at=192;previous=raw[160:192];n=0
    while at<len(raw):
        if len(raw)-at<112:break
        prefix=raw[at:at+112];assert prefix[:4]==b'JREC';kind,flags,header,length,sequence=struct.unpack_from('<HHIIQ',prefix,4);assert flags==1 and header==112 and sequence==n+1 and prefix[24:40]==bytes.fromhex(store['publisher_identity']) and struct.unpack_from('<Q',prefix,40)[0]==int(store['publisher_epoch']) and prefix[48:80]==previous
        if len(raw)-at<144+length:break
        payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length];assert hashlib.sha256(payload).digest()==prefix[80:112] and hashlib.sha256(raw[160:192]+prefix+payload).digest()==trailer;v=json.loads(payload);assert canonical(v)==payload
        if n<3:assert kind==n+1 and v==[definition,review,grant][n]
        else:assert v['restoration_digest']==digest
        n+=1;previous=trailer;at+=144+length
    return n

def history_expectation(case,before,prepared,review,grant,store):
    d=prepared['definition'];dg=prepared['restoration_digest'];rows=[(1,d),(2,review),(3,grant),(4,dict(schema='org.disked.gpt-restoration-admission/1',restoration_digest=dg,review_digest=sha(canonical(review)),grant_digest=sha(canonical(grant)),store=store))];images=[before];patch_by_id={p['id']:p for p in case['patches']}
    for i,p in enumerate(d['patches']):
        rows.append((5,dict(schema='org.disked.gpt-restoration-event/1',restoration_digest=dg,event='intention',prefix=str(i),image_digest=sha(images[-1]),patch=p)))
        raw=bytearray(images[-1]);original=patch_by_id[p['id']];raw[original['offset']:original['offset']+len(original['before'])]=original['before'];images.append(bytes(raw))
        rows.append((6,dict(schema='org.disked.gpt-restoration-event/1',restoration_digest=dg,event='completion',prefix=str(i+1),image_digest=sha(images[-1]),patch=p)))
    rows.append((9,dict(schema='org.disked.gpt-restoration-event/1',event='seal-restored-basis',restoration_digest=dg,prefix=str(len(d['patches'])),image_digest=sha(case['raw']))));return rows,images

def history_oracle(raw,case,before,prepared,review,grant,store):
    rows,images=history_expectation(case,before,prepared,review,grant,store);v=dict(disposition='not_started' if not raw else 'invalid',diagnostic='',records='0',verified_bytes='0',error_offset='0',bootstrap_records='0',confirmed_prefix='0',pending_intention=False,sealed=False)
    def bad(code,offset=0):v.update(disposition='invalid',diagnostic=code,error_offset=str(offset));return v
    if not raw:return v
    if len(raw)<192:return bad('journal_header_incomplete')
    if raw[:8]!=b'DEJPR001':return bad('journal_magic')
    if struct.unpack_from('<HH',raw,8)!=(1,0):return bad('journal_version')
    if struct.unpack_from('<I',raw,12)[0]!=192 or struct.unpack_from('<I',raw,20)[0]!=65536:return bad('journal_header_profile')
    if any(raw[16:20]+raw[136:160]):return bad('journal_header_flags')
    if hashlib.sha256(raw[:160]).digest()!=raw[160:192]:return bad('journal_header_checksum')
    d=prepared['definition'];binding=bytes.fromhex(store['identity'][7:])[:16]+bytes.fromhex(prepared['restoration_digest'][7:])+hashlib.sha256(canonical(dict(original=d['resources'],recovery_store=store))).digest()+hashlib.sha256(canonical(dict(provider=d['resources']['provider_id'],executor=store['executor_digest']))).digest()
    if raw[24:136]!=binding:return bad('journal_binding_mismatch')
    at=192;previous=raw[160:192];v['verified_bytes']='192'
    while at<len(raw):
        if v['sealed']:return bad('journal_after_terminal',at)
        if len(raw)-at<112:v.update(disposition='torn_tail',diagnostic='journal_final_prefix_incomplete',error_offset=str(at));return v
        prefix=raw[at:at+112]
        if prefix[:4]!=b'JREC':return bad('journal_record_magic',at)
        kind,flags,header,length,sequence=struct.unpack_from('<HHIIQ',prefix,4)
        if header!=112:return bad('journal_prefix_length',at)
        if length>65536:return bad('journal_payload_limit',at)
        if flags>1:return bad('journal_record_flags',at)
        if 1<=kind<=9 and flags!=1:return bad('journal_critical_bit',at)
        if kind==32769 and flags!=0:return bad('journal_observation_flags',at)
        if kind not in range(1,10) and kind!=32769 and (flags!=0 or kind<32768):return bad('journal_unknown_kind',at)
        if not any(prefix[24:40]) or not struct.unpack_from('<Q',prefix,40)[0]:return bad('journal_record_identity',at)
        if sequence!=int(v['records'])+1:return bad('journal_sequence',at)
        if prefix[48:80]!=previous:return bad('journal_previous_digest',at)
        if len(raw)-at<144+length:v.update(disposition='torn_tail',diagnostic='journal_final_record_incomplete',error_offset=str(at));return v
        payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length]
        if hashlib.sha256(payload).digest()!=prefix[80:112]:return bad('journal_payload_checksum',at)
        if hashlib.sha256(raw[160:192]+prefix+payload).digest()!=trailer:return bad('journal_record_checksum',at)
        n=int(v['records'])
        if prefix[24:40]!=bytes.fromhex(store['publisher_identity']) or struct.unpack_from('<Q',prefix,40)[0]!=int(store['publisher_epoch']) or n>=len(rows) or kind!=rows[n][0] or payload!=canonical(rows[n][1]):return bad('journal_semantic_rejected',at)
        v['records']=str(n+1);v['bootstrap_records']=str(min(n+1,4))
        if kind==5:v['pending_intention']=True
        elif kind==6:v['pending_intention']=False;v['confirmed_prefix']=str(int(v['confirmed_prefix'])+1)
        elif kind==9:v['sealed']=True
        at+=144+length;previous=trailer;v['verified_bytes']=str(at)
    v.update(disposition='valid_prefix',error_offset='0');return v

def inspect_fixture(probe,data,prepared,review,grant,store,before,old_journal,mutate=None,fault=None):
    owned=data['owned'];prior={p.name:p.read_bytes() for p in owned.iterdir()};case=data['case']
    call=request(case,data['source'],'restore-inspect',manifest=data['preparation']['manifest'],review=data['review'],grant=data['grant'],restoration_definition=prepared['definition'],restoration_digest=prepared['restoration_digest'],restoration_review=review,restoration_grant=grant,restoration_store=store)
    if fault:call['fault']=fault
    lines=copy.deepcopy([call,dict(phase='retained-observation',image_hex=before.hex()),dict(phase='retained-original-journal',journal_hex=old_journal.hex())])
    if mutate:mutate(lines)
    result=subprocess.run([str(probe)],input=b''.join(canonical(v)+b'\n' for v in lines),capture_output=True,timeout=15);assert not result.stderr
    assert prior=={p.name:p.read_bytes() for p in owned.iterdir()},'Inspection changed owned artifacts'
    output=json.loads(result.stdout)
    if result.returncode==0:
        assert output['phase']=='restoration_inspected' and not any('.write.' in x['stage'] or '.flush.' in x['stage'] for x in output['events'])
        v=output['inspection'];oracle=history_oracle(prior[store['name']],case,before,prepared,review,grant,store);assert v['journal']==oracle,(v['journal'],oracle)
        _,images=history_expectation(case,before,prepared,review,grant,store);current=prior['image.bin'];d=prepared['definition'];assert v['matching_prefixes']==[str(i) for i,b in enumerate(images) if b==current]
        assert v['image_digest']==sha(current) and v['current_original_image']==(current==case['raw']) and v['backup_exact']==(sha(prior['backup.bin'])==d['backup_digest']) and v['original_journal_unchanged']==(prior['journal.bin']==old_journal)
        assert v['current_known_bytes']==all(a in (b,c) for a,b,c in zip(current,before,case['raw']))
        matches=oracle['sealed'] and oracle['disposition']=='valid_prefix' and current==images[int(oracle['confirmed_prefix'])] and v['backup_exact'] and v['original_journal_unchanged'];assert v['current_matches_seal']==matches and v['reconciliation_required']==(not matches)
        assert all(not v[k] for k in ('authorizes_effects','product_writes_admitted','qualifies_power_loss','qualifies_recovery'))
    else:assert result.returncode==3 and output['phase']=='refused'
    return result.returncode,output

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--evidence',type=Path);ap.add_argument('--trace-io',action='store_true');a=ap.parse_args();a.probe=a.probe.resolve();a.root=a.root.resolve();records=[];passed=False;probe_sha=sha(a.probe.read_bytes());observations=[];fixture_state={}
    probe_env=os.environ.copy();probe_env.pop('DISKED_GPT_FIXTURE_TRACE',None)
    if a.trace_io:probe_env['DISKED_GPT_FIXTURE_TRACE']='1'
    def record(name,**data):records.append(dict(name=name,**data));print('CASE '+ascii(name),flush=True)
    def make(parent,name,case,source='primary',fault=None,cancel='none'):
        folder=parent/name;folder.mkdir();process=subprocess.Popen([str(a.probe),'--fixture-parent',str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=probe_env);rows=Replies(process)
        try:
            v=request(case,source)
            if fault:v['fault']=fault
            send(process,v);prepared=rows.get(timeout=15,phase=name+':preparation');assert prepared['phase']=='prepared' and prepared['definition']==case['definition'];review,grant=receipts(prepared);send(process,dict(phase='execute',review=review,grant=grant,cancel_at=cancel));process.stdin.close();finish=rows.get(timeout=15,phase=name+':execution');code=rows.wait(timeout=15,phase=name+':exit');rows.assert_drained(a.trace_io)
            assert code in (0,3,6,112),(code,finish);owned=Path(prepared['manifest']['directory']);assert owned.is_relative_to(folder);return dict(preparation=prepared,review=review,grant=grant,owned=owned,case=case,source=source,original_code=code)
        finally:close(process,rows,observations)
    def restore(name,fixture_data,fault=None,mutate=None,change_after_review=None,expect_refusal=None,attempt=None,expect_effect_refusal=None):
        case=fixture_data['case'];owned=fixture_data['owned'];image=owned/'image.bin';before=image.read_bytes();old_artifacts={p.name:p.read_bytes() for p in owned.iterdir() if p.name!='image.bin'};files_before=set(old_artifacts);attempt=attempt or uuid.uuid4().hex
        v=request(case,fixture_data['source'],'restore',manifest=fixture_data['preparation']['manifest'],review=fixture_data['review'],grant=fixture_data['grant'],attempt_id=attempt)
        if fault:v['fault']=fault
        process=subprocess.Popen([str(a.probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=probe_env);rows=Replies(process);prepared=store=finish=None;review=grant=None;fixture_added=set()
        try:
            send(process,v);first=rows.get(timeout=15,phase=name+':restoration-preparation')
            if first and first['phase']=='restoration_prepared':
                prepared=first;d=prepared['definition'];assert d['patches']==expected_patches(case,before) and d['original_image_digest']==sha(case['raw']) and d['observed_image_digest']==sha(before) and d['backup_digest']==sha(old_artifacts['backup.bin']) and d['original_journal_digest']==sha(old_artifacts['journal.bin']) and d['resources']==fixture_data['preparation']['manifest'];assert prepared['restoration_digest']==sha(canonical(d));assert not prepared['execution_authorized'] and not any('.write.' in e['stage'] or '.flush.' in e['stage'] for e in prepared['events'])
                assert set(p.name for p in owned.iterdir())==files_before|{'image.bin'}
                review,grant=recovery_receipts(prepared);instruction=dict(phase='restore-execute',review=copy.deepcopy(review),grant=copy.deepcopy(grant))
                if mutate:mutate(instruction)
                if change_after_review:
                    change_after_review(owned);fixture_added={p.name for p in owned.iterdir()}-files_before-{'image.bin'}
                send(process,instruction);process.stdin.close();next_row=rows.get(timeout=15,phase=name+':restoration-store')
                if next_row and next_row['phase']=='restoration_store':store=next_row['store'];finish=rows.get(timeout=15,phase=name+':restoration-execution')
                else:finish=next_row
            else:finish=first;process.stdin.close()
            code=rows.wait(timeout=15,phase=name+':restoration-exit');rows.assert_drained(a.trace_io)
            while not rows.empty():assert rows.get_nowait() is None
            current=image.read_bytes();new_files={p.name for p in owned.iterdir()}-files_before-{'image.bin'}-fixture_added
            for file,data in old_artifacts.items():assert (owned/file).read_bytes()==data,'Changed retained artifact '+file
            if expect_refusal:
                assert code==3 and finish['phase']=='refused' and finish['diagnostic']==expect_refusal,(code,finish)
                assert current==before and not new_files
            elif mutate:
                assert code==3 and finish['phase']=='refused' and current==before and not new_files
            elif code==0:
                assert finish['phase']=='restoration_finished' and finish['restoration']['status'] in ('restored_original_basis','unchanged') and current==case['raw']
                assert len(new_files)==1 and store and new_files=={store['name']}
            elif code in (3,6):
                assert finish['phase']=='restoration_finished' and finish['restoration']['status'] in ('refused','unresolved'),finish
                if fault:assert finish['fault_fired']
                if expect_effect_refusal:assert code==3 and finish['restoration']['diagnostic']==expect_effect_refusal and not finish['restoration']['possible_image_effects']
            else:assert code==112 and finish is None and fault
            if not change_after_review:
                assert all(now==old or any(int(p['offset'])<=i<int(p['offset'])+int(p['bytes']) for p in (prepared['definition']['patches'] if prepared else [])) for i,(now,old) in enumerate(zip(current,before))),'Changed outside restoration patches'
            raw=b''
            if store:
                raw=(owned/store['name']).read_bytes();journal(raw,prepared['definition'],prepared['restoration_digest'],review,grant,store)
            inspection=None
            if store:
                inspection_code,inspection=inspect_fixture(a.probe,fixture_data,prepared,review,grant,store,before,old_artifacts['journal.bin']);assert inspection_code==0
            record(name,exit_code=code,preparation=prepared,store=store,finish=finish,review=review,grant=grant,inspection=inspection,image_before_sha256=sha(before),image_after_sha256=sha(current),original_image_sha256=sha(case['raw']),journal_hex=raw.hex(),old_artifacts_sha256={n:sha(data) for n,data in old_artifacts.items()},fault=fault)
            return finish,prepared,store
        finally:close(process,rows,observations)
    try:
        parent=a.root/'.aide-local';parent.mkdir(exist_ok=True)
        with fixture_parent(a.root,fixture_state,observations) as directory:
            parent=Path(directory);assert parent.resolve().is_relative_to((a.root/'.aide-local').resolve())
            def case_for(unit=512,source='primary'):
                target='backup' if source=='primary' else 'primary';f=fixture(unit=unit);change_array(f,lambda b:b.__setitem__(0,b[0]^1),target,False)
                header=bytearray.fromhex(f[target]);header[16]^=1;f[target]=header.hex();return expected(f,source)
            normal=None;basic=case_for()
            for unit in (512,4096):
                for source in ('primary','backup'):
                    case=case_for(unit,source);data=make(parent,str(unit)+'-'+source,case,source,fault=dict(stage='image.write.2',action='crash_after'));result=restore(str(unit)+'-'+source,data)
                    if unit==512 and source=='primary':normal=result[0]
            stages=[e['stage'] for e in normal['events'] if '.write.' in e['stage'] or '.flush.' in e['stage']];assert stages and all(int(e['bytes'])<=65536 for e in normal['events'] if '.write.' in e['stage'])
            for index,stage in enumerate(stages):
                for action in ('crash_before','crash_after','before_error','after_error'):
                    name='restore-'+str(index)+'-'+action;data=make(parent,name,basic,fault=dict(stage='image.write.2',action='crash_after'));restore(name,data,fault=dict(stage=stage,action=action))
                if '.write.' in stage:
                    name='restore-'+str(index)+'-partial';data=make(parent,name,basic,fault=dict(stage='image.write.2',action='crash_after'));restore(name,data,fault=dict(stage=stage,action='partial_error'))
            for key in ['restoration_digest','review_digest','original_manifest_digest','executor_digest']:
                data=make(parent,'grant-'+key,basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-'+key,data,mutate=lambda v,key=key:v['grant'].__setitem__(key,sha(b'wrong')))
            for key in ['allow_fixture_restoration','allow_new_recovery_journal','acknowledge_nonatomic_same_volume']:
                data=make(parent,'grant-'+key,basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-'+key,data,mutate=lambda v,key=key:v['grant'].__setitem__(key,False))
            data=make(parent,'grant-scope',basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-scope',data,mutate=lambda v:v['grant'].__setitem__('patch_ids',[]))
            data=make(parent,'completed',basic);restore('completed-refused',data,expect_refusal='restoration_completed_operation')
            data=make(parent,'cancelled',basic,cancel='after-first-patch');restore('cancelled-prefix',data)
            data=make(parent,'before-effects',basic,fault=dict(stage='image.write.1',action='crash_before'));restore('already-original',data)
            data=make(parent,'foreign',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'image.bin';raw=bytearray(p.read_bytes());raw[20*512]=0x80;p.write_bytes(raw);restore('foreign-byte-refused',data,expect_refusal='restoration_foreign_bytes')
            data=make(parent,'backup',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'backup.bin';p.write_bytes(p.read_bytes()[:-1]);restore('backup-refused',data,expect_refusal='restoration_backup_invalid')
            data=make(parent,'history',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'journal.bin';raw=bytearray(p.read_bytes());raw[160]^=1;p.write_bytes(raw);restore('history-refused',data,expect_refusal='restoration_history_invalid')
            data=make(parent,'repeated',basic,fault=dict(stage='image.write.1',action='crash_after'));restore('repeated-first',data,fault=dict(stage='image.write.1',action='partial_error'));restore('repeated-second',data)
            # A grant binds the reviewed full snapshot, not merely object IDs.
            data=make(parent,'stale-snapshot',basic,fault=dict(stage='image.write.1',action='crash_after'))
            def alter_snapshot(root):
                p=root/'image.bin';v=bytearray(p.read_bytes());v[20*512]^=0x80;p.write_bytes(v)
            restore('snapshot-changed-after-review',data,change_after_review=alter_snapshot,expect_effect_refusal='restoration_snapshot_changed')
            data=make(parent,'swapped-after-review',basic,fault=dict(stage='image.write.1',action='crash_after'))
            def replace_object(root):
                p=root/'image.bin';v=p.read_bytes();p.rename(root/'retired-image.bin');p.write_bytes(v)
            restore('identity-changed-after-review',data,change_after_review=replace_object,expect_refusal='fixture_file_changed')
            data=make(parent,'journal-collision',basic,fault=dict(stage='image.write.2',action='crash_after'));attempt=uuid.uuid4().hex
            restore('journal-collision-first',data,fault=dict(stage='recovery.write.1',action='partial_error'),attempt=attempt);restore('journal-collision-refused',data,attempt=attempt,expect_refusal='fixture_open')
            # Partial large-array restoration must retain old image and journals
            # outside its exact reverse patch, then admit only a new fresh plan.
            f=fixture(blocks=8192,count=1024,size=1024);f['backup_array']=bytes(b^0x5a for b in bytes.fromhex(f['backup_array'])).hex();large=expected(f)
            for index,stage in enumerate(['image.write.8','image.write.16','image.flush.1']):
                data=make(parent,'large-'+str(index),large,fault=dict(stage='image.write.16',action='crash_after'))
                restore('large-interruption-'+str(index),data,fault=dict(stage=stage,action='crash_after'));restore('large-restoration-'+str(index),data)
        passed=True
    finally:
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),probe_sha256=probe_sha,records=records,fixture=fixture_state,process_observations=observations,diagnostic_io=a.trace_io),indent=2)+'\n',encoding='utf8',newline='\n')
    print('Owned GPT restoration PASS '+str(len(records)),flush=True)
if __name__=='__main__':main()
