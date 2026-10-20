"""Adapt the qualified guest cap setup for the ordinary-token experiment."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIOR=HERE.parent/'2026-10-18-guest-capacity'

def once(text, before, after):
    if text.count(before)!=1:raise ValueError('Template identity changed: '+before[:90])
    return text.replace(before,after,1)

CREATE_ACTOR=r'''
    $actorName='DiskEdTest-'+$nonce.Substring(0,8)
    $actorDescription='DiskEd test '+$nonce
    if(Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue){throw 'Disposable actor already exists; no adoption.'}
    $actorJournal=Join-Path $scratch 'ordinary-actor.json'
    $actorState=@{phase='creating';name=$actorName;nonce=$nonce;description=$actorDescription}
    [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
    if(-not$ActorPassword-or$ActorPassword.Length-eq0){throw 'Owner-supplied guest test credential required.'}
    $actorSecure=$ActorPassword
    $actorSecret=([Management.Automation.PSCredential]::new($actorName,$actorSecure)).GetNetworkCredential().Password
    $newActor=New-LocalUser -Name $actorName -Password $actorSecure -Description $actorDescription -PasswordNeverExpires -AccountNeverExpires
    $actorSid=$newActor.SID.Value
    Add-LocalGroupMember -SID ([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')) -Member $actorName
    $actorProfile='C:\Users\'+$actorName
    $actorProfileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actorSid
    if((Test-Path -LiteralPath $actorProfile)-or(Test-Path -LiteralPath $actorProfileKey)){throw 'Disposable actor unexpectedly has a profile.'}
    $actorState.phase='created';$actorState.sid=$actorSid
    [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
    $env:DISKED_TEST_ACTOR_NAME=$actorName
    $env:DISKED_TEST_ACTOR_PASS=$actorSecret
    $env:DISKED_TEST_ACTOR_SID=$actorSid
    $result.actor_name=$actorName;$result.actor_sid=$actorSid
'''

RETIRE_ACTOR=r'''
        if($actorName){
            Assert-WorkersStopped $workersStarted $workersStopped
            if($workersStarted){
                $proof=Get-Content -LiteralPath (Join-Path $root 'proof-result.json') -Raw|ConvertFrom-Json
                if(-not$proof.all_owned_processes_retired){throw 'Owned actor process retirement unverified.'}
                if($proof.scope-like'Per-image loader*' -and (-not$proof.image_registry_removed-or-not$proof.diagnostic_image_removed-or-not$proof.original_runtime_preserved)){
                    throw 'Preserve actor journal: diagnostic image/registry retirement unverified.'
                }
            }
            $actorCurrent=Get-Content -LiteralPath $actorJournal -Raw|ConvertFrom-Json
            if($actorCurrent.PSObject.Properties['object_namespace']-and$actorCurrent.object_namespace.phase-ne'retired'){throw 'Preserve actor/journal: object namespace retirement unverified.'}
            if($actorCurrent.PSObject.Properties['window_station']-and$actorCurrent.window_station.phase-ne'retired'){throw 'Preserve actor/journal: window-station exception retirement unverified.'}
            if($actorCurrent.PSObject.Properties['crypto_device']-and$actorCurrent.crypto_device.phase-ne'retired'){throw 'Preserve actor/journal: crypto-device exception retirement unverified.'}
            foreach($key in @('null_build','null_user')){if($actorCurrent.PSObject.Properties[$key]-and$actorCurrent.$key.phase-ne'retired'){throw 'Preserve actor/journal: null-sink exception retirement unverified.'}}
            $existing=Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue
            if($existing){
                if($existing.Description-ne$actorDescription-or($actorSid-and$existing.SID.Value-ne$actorSid)){throw 'Actor ownership changed; preserve account.'}
                if(-not$actorSid){$actorSid=$existing.SID.Value}
                $profile='C:\Users\'+$actorName
                $profileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actorSid
                if((Test-Path -LiteralPath $profile)-or(Test-Path -LiteralPath $profileKey)){throw 'Unexpected actor profile requires owned cleanup review.'}
                Remove-LocalUser -SID ([Security.Principal.SecurityIdentifier]::new($actorSid))
                if(Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue){throw 'Disposable actor removal did not complete.'}
                $actorState.phase='retired';$actorState.profile_absent=$true
                [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
            }
            $result.actor_removed=$true;$result.actor_profile_absent=$true
        }
'''

def main():
    work=Path(os.environ['DISKED_WORK_ROOT'])
    cleanup_only='--cleanup-only' in sys.argv
    null_proof='--null-proof' in sys.argv
    powershell_proof='--powershell-proof' in sys.argv
    powershell7_proof='--powershell7-proof' in sys.argv
    cleanup_proof='--cleanup-proof' in sys.argv
    ui_proof='--ui-proof' in sys.argv
    focus_fat='--focus-fat-review' in sys.argv
    focus_export='--focus-file-export' in sys.argv
    diagnose_history='--diagnose-fat-history' in sys.argv
    focus_history='--focus-fat-history' in sys.argv or diagnose_history
    focus_invocations='--focus-invocations' in sys.argv
    focus_repairs='--focus-qualification-repairs' in sys.argv
    focus_current='--focus-current-fixtures' in sys.argv
    focus_gui_watch='--focus-gui-watch' in sys.argv
    interactive_ui='--interactive-ui' in sys.argv
    native_memory='--native-memory' in sys.argv
    station_matrix='--station-bootstrap-matrix' in sys.argv
    object_trace='--object-startup-trace' in sys.argv
    if object_trace and not (interactive_ui and '--crypto-full' in sys.argv):
        raise ValueError('Owned object trace requires declared interactive primitive setup')
    if station_matrix and not (interactive_ui and '--crypto-full' in sys.argv):
        raise ValueError('Station matrix requires declared interactive primitive setup')
    full_native='--native-x64' in sys.argv or null_proof or powershell_proof or powershell7_proof or cleanup_proof or ui_proof or focus_fat or focus_export or focus_history or focus_invocations or focus_repairs or focus_current or focus_gui_watch
    controller_stop_proof='--controller-stop-proof' in sys.argv
    full_native=full_native or controller_stop_proof
    size=512 if '--size-mib=512' in sys.argv or full_native else 32
    if interactive_ui and not (full_native or native_memory or '--crypto-full' in sys.argv):
        raise ValueError('Interactive coordinator is restricted to declared primitive/native proofs')
    if size==512 and not ('--crypto-full' in sys.argv or full_native):raise ValueError('512MiB is restricted to its declared complete proof/native composition')
    if (HERE/'result.json').exists() and not cleanup_only:raise ValueError('Review and retain the previous attempt first')
    stage=work/'ordinary-proof';stage.mkdir()
    helper_files=('full-native.py','fixture-dacl.py','null-device.py','retire-temp.py','cleanup-probe.py','ui-probe.py','build-driver.py','guest-source.py','source-snapshot.py')
    full_files=helper_files+('pwsh7.zip','pwsh7.json','pydeps.zip','pydeps.json','source.pack','source.json')
    if full_native:
        for name in helper_files:
            origin=HERE/name if name in ('full-native.py','fixture-dacl.py','null-device.py','retire-temp.py','cleanup-probe.py','ui-probe.py') else ROOT/'tools'/name if name=='source-snapshot.py' else HERE.parent/'2026-10-18-guest-build'/name
            data=origin.read_bytes();ast.parse(data);(stage/name).write_bytes(data)
        shell_tool=powershell7_proof or focus_invocations or focus_current or '--native-x64' in sys.argv
        if shell_tool and '--prepare-only' not in sys.argv and not cleanup_only:
            definition=importlib.util.spec_from_file_location('powershell_setup',HERE/'prepare-powershell.py');tool=importlib.util.module_from_spec(definition);definition.loader.exec_module(tool)
            tool.prepare(stage)
        else:
            (stage/'pwsh7.zip').write_bytes(b'not-a-runtime');(stage/'pwsh7.json').write_text('{}\n')
        if '--prepare-only' in sys.argv or cleanup_only or null_proof or powershell_proof or powershell7_proof or cleanup_proof or ui_proof:
            (stage/'pydeps.zip').write_bytes(b'non-executable parser fixture');(stage/'pydeps.json').write_text('{}\n')
        else:
            ast.parse((HERE/'prepare-dependencies.py').read_bytes())
            definition=importlib.util.spec_from_file_location('schema_setup',HERE/'prepare-dependencies.py');dependencies=importlib.util.module_from_spec(definition);definition.loader.exec_module(dependencies)
            dependencies.prepare(ROOT,stage,work)
        if '--prepare-only' in sys.argv or cleanup_only:
            (stage/'source.pack').write_bytes(b'not-an-executable-qualification-pack');(stage/'source.json').write_text('{}\n')
        else:
            revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            context=json.loads((ROOT/'.aide-local/context/current/manifest.json').read_bytes())
            if context['work_id']!='DE-W105' or context['git_head']!=revision:raise ValueError('Exact work context required')
            definition=importlib.util.spec_from_file_location('full_snapshot',ROOT/'tools/source-snapshot.py');snapshot=importlib.util.module_from_spec(definition);definition.loader.exec_module(snapshot)
            selected=snapshot.selected_inputs(ROOT,'DE-W105',revision=revision)
            source=snapshot.export(ROOT,selected,work/'source-export',work,revision=revision)
            for name in full_files[-2:]:shutil.copyfile(work/'source-export'/name,stage/name)
        definition=importlib.util.spec_from_file_location('coordinator_workspace',ROOT/'tools/workspace.py');storage=importlib.util.module_from_spec(definition);definition.loader.exec_module(storage)
        for path in (work/'source-export',work/'schema-dependencies'):
            if path.exists():storage.remove_owned_work(path,work,path.name)
    for name in ('ordinary-worker.py','target.py','guest-proof.py','loader-observer.py','loader-forensics.py','crypto-device.py'):
        data=(HERE/name).read_bytes();ast.parse(data);(stage/name).write_bytes(data)
    if interactive_ui:
        shutil.copyfile(HERE/'interactive-run.ps1',stage/'interactive-run.ps1')
        data=(HERE/'window-station.py').read_bytes();ast.parse(data);(stage/'window-station.py').write_bytes(data)
        data=(HERE/'object-namespace.py').read_bytes();ast.parse(data);(stage/'object-namespace.py').write_bytes(data)
        if not full_native:shutil.copyfile(HERE/'ui-probe.py',stage/'ui-probe.py')
    native='--native-journey' in sys.argv
    native_files=('source/platform/windows/worker_files.h','source/runtime/command/json.h','source/runtime/command/json.cpp','source/portable/hash/sha256.h','source/portable/hash/sha256.cpp','source/providers/image/local_file.h','source/providers/image/local_file.cpp')
    if native:
        for name in ('native-journey.py','native-journey.cpp'):
            data=(HERE/name).read_bytes()
            if name.endswith('.py'):ast.parse(data)
            (stage/name).write_bytes(data)
        for path in native_files:
            target=stage/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/path).read_bytes())
    memory_files=('source/platform/windows/memory_budget.cpp','source/platform/windows/memory_budget.h','tests/frontend/gui_fixture.py')
    if native_memory:
        for name in ('memory-journey.py','memory-journey.cpp','memory-desktop-driver.py'):shutil.copyfile(HERE/name,stage/name)
        ast.parse((stage/'memory-journey.py').read_bytes())
        for path in memory_files:
            target=stage/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/path).read_bytes())
    expected=json.loads((HERE.parent/'2026-10-18-guest-build/ordinary-token-expectations.json').read_bytes())
    expected.update(experiment='ordinary-token-'+str(size)+'mib',source_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),initial_only_mib=size)
    if interactive_ui:
        expected['interactive_ui']=True
        expected['interactive_scope']='Agents session3 coordinator;fresh restricted actor on owned Medium hidden desktop;temporary journaled0x2016b station-only subject ACE with setup-fault recovery and exact retirement;EXITWINDOWS right required for User32 startup but no exit/logoff invocation;no filesystem/token/product-record change'
        expected['interactive_worker_review']=json.loads((HERE/'interactive-worker-plan.json').read_bytes())
        if object_trace:expected['object_startup_trace_only']=True
        if station_matrix:
            expected['station_bootstrap_matrix_only']=True
            expected['interactive_scope']='Six fixed trusted standard-user startup-only station UI-right observations;exact subject ACE retired after each;no restricted worker/product admission,security-edit rights or actual clipboard/screen/logoff actions'
    diagnostic='--diagnostic' in sys.argv
    startup_diagnostic='--startup-diagnostic' in sys.argv
    loader_diagnostic='--loader-diagnostic' in sys.argv
    forensic='--loader-forensics' in sys.argv
    namespace='--namespace-diagnostic' in sys.argv
    crypto_full='--crypto-full' in sys.argv
    crypto='--crypto-device' in sys.argv or crypto_full or native or full_native or native_memory
    if crypto:expected['crypto_device']=json.loads((HERE/'crypto-device-expectations.json').read_bytes())
    if crypto_full:expected['crypto_full']=json.loads((HERE/'crypto-full-expectations.json').read_bytes())
    if size==512:expected['composition_proof']=json.loads((HERE/'composition512-expectations.json').read_bytes())
    if native:expected['native_journey']=json.loads((HERE/'native-journey-expectations.json').read_bytes())
    if native_memory:expected['native_memory']=json.loads((HERE/'memory-journey-expectations.json').read_bytes())
    if full_native:
        expected['native_x64']=json.loads((HERE/'native-x64-expectations.json').read_bytes())
        expected['native_x64']['fixture_io_review']=json.loads((ROOT/expected['native_x64']['fixture_io_profile']).read_bytes())
    if full_native:
        # The transferred runtime zip is removed on the host before guest work
        # starts. Account for all remaining host scratch and current context in
        # the guest's aggregate watchdog as well as its filesystem capacity.
        reserved=storage.tree_bytes(work,allocated=True,file_limit=20000,allow_links=False)
        reserved+=storage.tree_bytes(ROOT/'.aide-local',allocated=True,file_limit=20000,allow_links=False)
        reserved-=storage.stored_bytes(stage/'pwsh7.zip',(stage/'pwsh7.zip').stat())
        expected['native_x64']['host_disposable_reserved_bytes']=reserved+1024*1024
    if null_proof or powershell_proof or powershell7_proof or cleanup_proof or ui_proof:expected['native_x64']['null_proof_only']=True
    if powershell_proof or powershell7_proof:expected['native_x64']['powershell_proof']=True
    if powershell7_proof:expected['native_x64']['powershell7_proof']=True
    if cleanup_proof:expected['native_x64']['cleanup_proof']=True
    if controller_stop_proof:
        expected['native_x64']['controller_stop_proof']=True
        expected['native_x64']['null_proof_only']=True
    if ui_proof:expected['native_x64']['ui_proof']=True
    if focus_fat:
        expected['native_x64']['focus_groups']=['acquisition.fat_tree_review']
        expected['native_x64']['focus_targets']=['fat_tree_review_probe','fat_tree_extraction_worker_probe']
    if focus_export:
        expected['native_x64']['focus_groups']=['evidence.file_export']
        expected['native_x64']['focus_targets']=['file_report_export_probe','file_report_export_fault','fat_tree_extraction_worker_probe']
    if focus_history:
        expected['native_x64']['focus_groups']=['evidence.fat_tree_history']
        expected['native_x64']['focus_targets']=['fat_tree_history_probe','fat_tree_extraction_probe','fat_tree_extraction_worker_probe','fat_tree_extraction_worker_fault']
        expected['native_x64']['trace_fat_history']=True
    if diagnose_history:
        expected['native_x64']['diagnose_fat_history']=True
        expected['native_x64']['history_diagnostic_seconds']=600
        expected['native_x64']['history_timing_review']=json.loads((HERE/'history-timing-review.json').read_bytes())
    if focus_invocations:
        expected['native_x64']['focus_groups']=['disked.invocation','disked_provider_guard.invocation',
            'disked.shell_invocation','disked_provider_guard.shell_invocation']
        expected['native_x64']['focus_targets']=['disked','disked_provider_guard','fat_tree_extraction_worker_probe']
    if focus_repairs:
        expected['native_x64']['focus_groups']=['evidence.logical_extraction','evidence.verification_commands',
            'frontend.acquisition_forms','frontend.acquisition_interactive','frontend.acquisition_timeout','frontend.fat_extraction']
        expected['native_x64']['focus_targets']=['disked','gui_model_probe','tui_model_probe',
            'verification_command_probe','verification_command_fault','shell_model_probe','watch_probe',
            'disked_image_test','acquisition_command_probe','fat_worker_probe','acquisition_case_probe',
            'acquired_image_verification_probe','image_verification_collection_probe','fat_tree_extraction_worker_probe']
        expected['native_x64']['focus_executables']=['disked','fat_tree_extraction_worker_probe']
        expected['native_x64']['ui_fixture_preflight']=True
    if focus_current:
        expected['native_x64']['focus_groups']=[
            'frontend.fat_recursive_failures','frontend.gui_capture','image.fat_commands',
            'image.fat_extraction','image.fat_tree_admission','image.fat_tree_controller',
            'image.file_acquisition','image.file_capture','image.ntfs_commands',
            'image.ntfs_directory_commands','image.ntfs_membership_commands','image.parent_pins',
            'operation.directory_pins','operation.watch','operation.worker',
            'resilience.console_waiting','resilience.output_waiting','shell.windows']
        expected['native_x64']['focus_targets']=[
            'acquisition_worker_fault','acquisition_worker_probe','disked','disked_fat_test',
            'disked_file_wait','disked_ntfs_test','disked_provider_guard','disked_recursive_disabled',
            'disked_recursive_fault','disked_tui_fault','disked_worker_delayed',
            'fat_tree_admission_fault','fat_tree_admission_probe','fat_tree_controller_fault',
            'fat_tree_controller_probe','fat_tree_reconnect_probe','fat_worker_probe',
            'file_acquisition_fault','file_acquisition_probe','image_file_capture_fault',
            'image_file_capture_probe','image_observation_probe','ntfs_inspection_probe',
            'ntfs_worker_probe','worker_directory_probe','fat_tree_extraction_worker_probe',
            'fat_tree_extraction_worker_fault']
        expected['native_x64']['focus_executables']=['disked','fat_tree_extraction_worker_probe']
        expected['native_x64']['ui_fixture_preflight']=True
    if focus_gui_watch:
        expected['native_x64']['focus_groups']=['frontend.gui_capture','operation.watch']
        expected['native_x64']['focus_targets']=['disked','disked_file_wait','fat_tree_extraction_worker_probe']
        expected['native_x64']['focus_executables']=['disked','fat_tree_extraction_worker_probe']
        expected['native_x64']['ui_fixture_preflight']=True
    if namespace:expected['namespace_diagnostic']=json.loads((HERE/'namespace-expectations.json').read_bytes())
    if forensic:expected['loader_forensics']=json.loads((HERE/'forensic-expectations.json').read_bytes())
    if loader_diagnostic:expected['loader_diagnostic']=json.loads((HERE/'loader-expectations.json').read_bytes())
    if startup_diagnostic:
        expected['startup_diagnostic']=json.loads((HERE/'startup-diagnostic-expectations.json').read_bytes())
    if diagnostic:
        expected['launch_diagnostic']=json.loads((HERE/'launch-diagnostic-expectations.json').read_bytes())
        expected.update(experiment='WithToken startup parameter isolation',variants=expected['launch_diagnostic']['variants'],
            admission='Diagnostic only. Each successful child must report its actual restricted nonelevated/non-AppContainer token. No excluded canary or undeclared standard handle may reach a candidate. Full protected-record,capacity,outside-write and interruption checks remain pending.')
    else:expected['selected_profile']=json.loads((HERE/'full-profile-expectations.json').read_bytes())
    (stage/'expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8',newline='\n')
    setup=(PRIOR/'guest-proof.ps1').read_text()
    setup=once(setup,'[int]$SizeMiB=32)','[int]$SizeMiB=32,[Security.SecureString]$ActorPassword)')
    setup=once(setup,"$environmentVerified=$false","$environmentVerified=$false\n$actorName=$null;$actorSid=$null;$actorDescription=$null")
    marker=next(line for line in setup.splitlines() if "[IO.File]::WriteAllText((Join-Path $scratch 'owner.json')" in line)
    setup=once(setup,marker,marker+'\n'+CREATE_ACTOR)
    setup=once(setup,"actor_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
               "actor_sid=$actorSid;build_user_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value" if full_native else "actor_sid=$actorSid")
    if diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --diagnostic 2>&1)")
    if startup_diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --startup-diagnostic 2>&1)")
    if loader_diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --loader-diagnostic 2>&1)")
    if forensic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --loader-forensics 2>&1)")
    if namespace:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --namespace-diagnostic 2>&1)")
    if crypto:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') "+('--native-x64' if full_native else '--native-memory' if native_memory else '--native-journey' if native else '--crypto-full' if crypto_full else '--crypto-device')+" 2>&1)")
    if interactive_ui:
        line=next(line for line in setup.splitlines() if '$log=@(& $python -B' in line)
        setup=once(setup,line+'\n        $code=$LASTEXITCODE',
            "        $dispatch=& ([scriptblock]::Create([IO.File]::ReadAllText((Join-Path $root 'interactive-run.ps1'))))\n        $log=@($dispatch.output)\n        $code=[int]$dispatch.exit_code\n        $result.interactive_dispatch=$dispatch.metadata")
    setup=once(setup,"[Security.Principal.SecurityIdentifier]::new('S-1-15-2-1')","[Security.Principal.SecurityIdentifier]::new($actorSid)")
    if full_native:
        setup=once(setup,'$acl.AddAccessRule($readRule);Set-Acl -LiteralPath $volumeRoot -AclObject $acl',
            "$acl.AddAccessRule($readRule)\n    $packageRead=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($attach.profiles[0].sid),[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)\n    $acl.AddAccessRule($packageRead);Set-Acl -LiteralPath $volumeRoot -AclObject $acl")
    setup=once(setup,'        if($attached){',RETIRE_ACTOR+'\n        if($attached){')
    setup=once(setup,"    $result.finished_at=[DateTime]::UtcNow.ToString('o')", "    $env:DISKED_TEST_ACTOR_NAME=$null;$env:DISKED_TEST_ACTOR_PASS=$null;$env:DISKED_TEST_ACTOR_SID=$null\n    $actorSecret=$null;$actorSecure=$null\n    $result.finished_at=[DateTime]::UtcNow.ToString('o')")
    (stage/'guest-proof.ps1').write_text(setup,encoding='utf-8',newline='\n')
    attach=(PRIOR/'attach-image.py').read_text()
    attach=once(attach,"(A;;GA;;;' + config['actor_sid']", "(A;;0x1301bf;;;' + config['actor_sid']")
    if full_native:attach=once(attach,"config['actor_sid'] + ')' +", "config['actor_sid'] + ')' + '(A;;0x1301bf;;;' + config['build_user_sid'] + ')' +")
    attach=once(attach,"''.join('(A;;0x1301bf;;;' + p['sid'] + ')' for p in profiles)",
                "''.join('(A;;0x1301bf;;;' + p['sid'] + ')' for p in profiles[:1])" if full_native else "''")
    ast.parse(attach);(stage/'attach-image.py').write_text(attach,encoding='utf-8',newline='\n')
    root_line="$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\\..\\..'))"
    fixed_root="$root='"+str(ROOT).replace("'","''")+"'"
    host=once((PRIOR/'run-proof.ps1').read_text(),root_line,fixed_root)
    host=once(host,'org.disked.guest-capacity-campaign/1','org.disked.ordinary-token-campaign/1')
    host=once(host,"    $job=Invoke-Command -Session $session -AsJob", "    $credentialPath=Join-Path $env:LOCALAPPDATA 'DiskEd\\credentials\\vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml'\n    $testCredential=Import-Clixml -LiteralPath $credentialPath\n    if($testCredential-isnot[Management.Automation.PSCredential]-or$testCredential.UserName-notmatch'^(?:(?:\\.|BLACKGLASS-HYPE|BLACKGLASS-HYPERV)\\\\)?Agents$'){throw 'Expected protected Agents credential required.'}\n    $job=Invoke-Command -Session $session -AsJob")
    host=once(host,'-ArgumentList $true,$SizeMiB','-ArgumentList $true,$SizeMiB,$testCredential.Password')
    host=once(host,'    if($session){Remove-PSSession -Session $session}','    if($session){Remove-PSSession -Session $session}\n    $testCredential=$null')
    host=once(host,"        @{host=(Join-Path $PSScriptRoot 'guest-proof.py');relative='guest-proof.py'},", "        @{host=(Join-Path $PSScriptRoot 'ordinary-worker.py');relative='ordinary-worker.py'},\n        @{host=(Join-Path $PSScriptRoot 'target.py');relative='target.py'},\n        @{host=(Join-Path $PSScriptRoot 'guest-proof.py');relative='guest-proof.py'},")
    host=once(host,'    $selected=@(',"    $selected=@(\n        @{host=(Join-Path $PSScriptRoot 'loader-forensics.py');relative='loader-forensics.py'},\n        @{host=(Join-Path $PSScriptRoot 'loader-observer.py');relative='loader-observer.py'},")
    host=once(host,'    $selected=@(',"    $selected=@(\n        @{host=(Join-Path $PSScriptRoot 'crypto-device.py');relative='crypto-device.py'},")
    if interactive_ui:
        selected=('interactive-run.ps1','window-station.py','object-namespace.py') if full_native else ('interactive-run.ps1','window-station.py','object-namespace.py','ui-probe.py')
        rows='\n'.join("        @{host=(Join-Path $PSScriptRoot '"+path+"');relative='"+path+"'}," for path in selected)
        host=once(host,'    $selected=@(','    $selected=@(\n'+rows)
    if native:
        selected=('native-journey.py','native-journey.cpp')+native_files
        rows='\n'.join("        @{host=(Join-Path $PSScriptRoot '"+path+"');relative='"+path+"'}," for path in selected)
        host=once(host,'    $selected=@(','    $selected=@(\n'+rows)
        host=once(host,'Copy-VMFile -VM $vm -FileSource Host -SourcePath $file.host','Copy-VMFile -VM $vm -FileSource Host -CreateFullPath -SourcePath $file.host')
    if native_memory:
        selected=('memory-journey.py','memory-journey.cpp','memory-desktop-driver.py')+memory_files
        rows='\n'.join("        @{host=(Join-Path $PSScriptRoot '"+path+"');relative='"+path+"'}," for path in selected)
        host=once(host,'    $selected=@(','    $selected=@(\n'+rows)
        host=once(host,'Copy-VMFile -VM $vm -FileSource Host -SourcePath $file.host','Copy-VMFile -VM $vm -FileSource Host -CreateFullPath -SourcePath $file.host')
    if full_native:
        rows='\n'.join("        @{host=(Join-Path $PSScriptRoot '"+path+"');relative='"+path+"'}," for path in full_files)
        host=once(host,'    $selected=@(','    $selected=@(\n'+rows)
        host=once(host,"    # Send trusted local source as a remoting script; do not alter guest policy.",r'''    $transfer=Join-Path $PSScriptRoot 'pwsh7.zip'
    $transferFile=Get-Item -LiteralPath $transfer
    if($transferFile.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked host transfer file.'}
    $row=@($files|Where-Object path -eq 'pwsh7.zip')[0]
    $remoteHash=Invoke-Command -Session $session -ScriptBlock {
        (Get-FileHash -LiteralPath 'C:\ProgramData\DiskEd\qualification\pwsh7.zip' -Algorithm SHA256).Hash
    }
    if($remoteHash-ne$row.sha256){throw 'Guest runtime transfer differs from the prepared bytes.'}
    Remove-Item -LiteralPath $transfer -Force
    $result.host_runtime_transfer_removed=@{bytes=$row.bytes;sha256=$row.sha256;removed=$true}
    # Send trusted local source as a remoting script; do not alter guest policy.''')
    start=host.index("        $python='C:\\ProgramData\\DiskEd\\python314'")
    end=host.index('        New-Item -ItemType Directory',start)
    host=host[:start]+host[end:]
    host=once(host,"    foreach($file in $selected)","    $backing=@(Get-VMHardDiskDrive -VM $vm);if($backing.Count-ne1){throw 'Unexpected VM backing topology.'}\n    $backingPath=$backing[0].Path;$result.host_backing_start_bytes=(Get-Item -LiteralPath $backingPath).Length\n    foreach($file in $selected)")
    if full_native:
        # A remoting-job stop can kill the interactive coordinator before its
        # finally blocks retire the journaled grants. First signal its existing
        # owned-job poll loop; leave only bounded cleanup, never more workload.
        host=once(host,'    $job=Invoke-Command',"    $controlSession=& (Join-Path $root 'tools\\connect-vm.ps1') -OpenSession\n    $job=Invoke-Command")
        host=once(host,'        Start-Sleep -Seconds 1',r'''        $growth=(Get-Item -LiteralPath $backingPath).Length-$result.host_backing_start_bytes
        $proofReady=$false
        if($controllerStopProof-and-not$result.resource_stop_requested){
            $proofReady=Invoke-Command -Session $controlSession -ScriptBlock {
                $p='C:\ProgramData\DiskEd\qualification\stop-ready.json'
                if(Test-Path -LiteralPath $p){$d=Get-Content -LiteralPath $p -Raw|ConvertFrom-Json;$state=Get-Content -LiteralPath 'C:\ProgramData\DiskEd\qualification\scratch\state.json' -Raw|ConvertFrom-Json;if($d.nonce-ne$state.nonce){throw 'Stop-proof ownership changed.'};$true}else{$false}
            }
        }
        if($growth-gt1GB-or$proofReady-or$result.resource_stop_requested){
            if(-not$result.resource_stop_requested){
                $reason=if($proofReady-and$growth-le1GB){'controller_probe'}else{'shared_backing_growth'}
                $signal=Invoke-Command -Session $controlSession -ArgumentList ([long]$growth),$reason -ScriptBlock {
                    param($Growth,$Reason)
                    $r='C:\ProgramData\DiskEd\qualification'
                    $state=Get-Content -LiteralPath "$r\scratch\state.json" -Raw|ConvertFrom-Json
                    $owner=Get-Content -LiteralPath "$r\scratch\owner.json" -Raw|ConvertFrom-Json
                    if($state.nonce-ne$owner.nonce-or$state.nonce-notmatch'^[0-9a-f]{32}$'){throw 'Stop ownership changed.'}
                    $request=@{schema='org.disked.guest-stop/1';nonce=$state.nonce;reason=$Reason;observed_growth_bytes=$Growth;limit_bytes=[long]1GB}
                    $path="$r\stop-request.json";$temporary="$r\stop-request.$($state.nonce).tmp"
                    if((Test-Path -LiteralPath $path)-or(Test-Path -LiteralPath $temporary)){throw 'Existing stop signal;no adoption.'}
                    [IO.File]::WriteAllText($temporary,($request|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
                    [IO.File]::Move($temporary,$path)
                    [pscustomobject]@{nonce=$state.nonce;reason=$Reason;observed_growth_bytes=$Growth;limit_bytes=[long]1GB}
                }
                $result.resource_stop_requested=$signal|Select-Object nonce,reason,observed_growth_bytes,limit_bytes
                $stopStarted=[DateTime]::UtcNow
            }
            $elapsed=([DateTime]::UtcNow-$stopStarted).TotalSeconds
            if($elapsed-gt30-and-not$result.resource_stop_acknowledged){
                $ack=Invoke-Command -Session $controlSession -ScriptBlock {
                    $p='C:\ProgramData\DiskEd\qualification\stop-acknowledged.json'
                    if(Test-Path -LiteralPath $p){Get-Content -LiteralPath $p -Raw|ConvertFrom-Json}
                }
                if(-not$ack-or$ack.nonce-ne$result.resource_stop_requested.nonce-or$ack.owned_job_processes_retired-ne$true){Stop-Job -Job $job;throw 'Guest stop was not acknowledged;inspect owned recovery state.'}
                $result.resource_stop_acknowledged=$ack|Select-Object nonce,owned_job_processes_retired,command
            }
            if($elapsed-gt300){Stop-Job -Job $job;throw 'Bounded guest cleanup did not finish;inspect owned recovery state.'}
        }
        Start-Sleep -Seconds 1''')
        host=once(host,'$session=$null','$session=$null;$controlSession=$null')
        host=once(host,'$controlSession=$null',"$controlSession=$null;$controllerStopProof="+('$true' if controller_stop_proof else '$false'))
        host=once(host,'    if($session){Remove-PSSession -Session $session}',
                  '    if($controlSession){Remove-PSSession -Session $controlSession}\n    if($session){Remove-PSSession -Session $session}')
    else:
        host=once(host,'        Start-Sleep -Seconds 1',"        if(((Get-Item -LiteralPath $backingPath).Length-$result.host_backing_start_bytes)-gt1GB){Stop-Job -Job $job;throw 'Shared backing growth reached campaign ceiling.'}\n        Start-Sleep -Seconds 1")
    host=once(host,"    if($result.guest.setup.status-ne'pass'", "    $result.host_backing_end_bytes=(Get-Item -LiteralPath $backingPath).Length\n    if(-not$result.guest.setup.actor_removed-or-not$result.guest.setup.actor_profile_absent){throw 'Actor/account cleanup unverified.'}\n    if($result.guest.setup.status-ne'pass'")
    if full_native:
        host=once(host,"    $result.host_backing_end_bytes=", "    $retained=Invoke-Command -Session $session -ScriptBlock { $p='C:\\ProgramData\\DiskEd\\qualification\\retained.tar.xz';if(Test-Path -LiteralPath $p){$f=Get-Item -LiteralPath $p;if($f.Length-gt32MB-or($f.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Invalid retained archive.'};$true}else{$false}}\n    if($retained){Copy-Item -FromSession $session -LiteralPath 'C:\\ProgramData\\DiskEd\\qualification\\retained.tar.xz' -Destination (Join-Path $PSScriptRoot 'retained.tar.xz')}\n    $result.host_backing_end_bytes=")
    (stage/'run-proof.ps1').write_text(host,encoding='utf-8',newline='\n')
    cleanup=once((PRIOR/'clean-proof.ps1').read_text(),root_line,fixed_root)
    cleanup=once(cleanup,'$paths=@($Expected',"$extra=@(\"$root\\scratch\\ordinary-actor.json\",\"$root\\scratch\\outside\\baseline\",\"$root\\scratch\\outside\\forbidden\",\"$root\\scratch\\outside\\descendant-forbidden\",\"$root\\scratch\\outside\\inheritance-canary.bin\")\n        $paths=$extra+@($Expected")
    cleanup=once(cleanup,'$items.Count-gt32','$items.Count-gt($paths.Count+$dirs.Count)')
    cleanup=once(cleanup,'        $items=@();',r'''        foreach($path in $paths){
            $parent=[IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($path))
            while($parent-ne$root){
                if(-not$parent.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup path escaped root.'}
                if($parent-notin$dirs){$dirs+=,$parent}
                $parent=[IO.Path]::GetDirectoryName($parent)
            }
        }
        $items=@();''')
    cleanup=once(cleanup,'foreach($path in @("$root\\scratch\\outside","$root\\scratch","$root\\tools",$root))','foreach($path in @($dirs|Sort-Object Length -Descending)+@($root))')
    if full_native:cleanup=once(cleanup,'$extra=@(',r'''$extra=@("$root\stop-ready.json","$root\stop-request.json","$root\stop-acknowledged.json","$root\source-owner.json","$root\source-prepared.json","$root\source-retired.json","$root\scoped-directory-access.json","$root\retained.tar.xz",''')
    if interactive_ui:cleanup=once(cleanup,'$extra=@(',r'''$extra=@("$root\interactive-input.xml","$root\interactive-result.json",''')
    (stage/'clean-proof.ps1').write_text(cleanup,encoding='utf-8',newline='\n')
    # Parse in Windows PowerShell 5.1 before any guest action.
    parser="$e=$null;$t=$null;foreach($f in Get-ChildItem -LiteralPath $args[0] -Filter '*.ps1'){$null=[Management.Automation.Language.Parser]::ParseFile($f.FullName,[ref]$t,[ref]$e);if($e.Count){throw ($e|Out-String)}}"
    check=subprocess.run([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-Command','& {'+parser+'} '+"'"+str(stage).replace("'","''")+"'"],capture_output=True,timeout=30)
    if check.returncode:raise RuntimeError(check.stderr.decode(errors='replace'))
    hashes={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}
    (HERE/'prepared.json').write_text(json.dumps(dict(status='pass',scope='Source/AST/template/Windows PowerShell5.1 parse only; no guest execution',generated_sha256=hashes),indent=2)+'\n',encoding='utf-8',newline='\n')
    if '--prepare-only' in sys.argv:return 0
    if cleanup_only:
        previous=json.loads((HERE/'result.json').read_bytes())
        if previous['guest']['setup']['size_mib']!=size:raise ValueError('Cleanup size differs from receipt')
        shutil.copyfile(HERE/'result.json',stage/('proof-'+str(size)+'.json'))
        cleaned=subprocess.run(['pwsh','-NoProfile','-File',str(stage/'clean-proof.ps1'),'-SizeMiB',str(size)],cwd=ROOT,capture_output=True,timeout=60)
        if cleaned.returncode:raise RuntimeError((cleaned.stdout+cleaned.stderr)[-16384:].decode(errors='replace'))
        shutil.copyfile(stage/'cleanups.json',HERE/'cleanup.json')
        return 0
    call=subprocess.run(['pwsh','-NoProfile','-File',str(stage/'run-proof.ps1'),'-SizeMiB',str(size)],cwd=ROOT,capture_output=True,timeout=9000 if full_native else 600)
    raw=(stage/('proof-'+str(size)+'.json')).read_bytes();result=json.loads(raw)
    result['generated_sha256']=hashes;result['host_exit_code']=call.returncode
    proof=result.get('guest',{}).get('proof') or {}
    result['experiment_kind']='launch-parameter diagnostic' if diagnostic else 'full ordinary-worker primitive proof'
    if startup_diagnostic:result['experiment_kind']='standard/restricted token and console diagnostic; no profile admission'
    if loader_diagnostic:result['experiment_kind']='minimal Python entry and native-import diagnostic; no profile admission'
    if forensic:result['experiment_kind']='owned per-image loader tracing; no profile admission'
    if namespace:result['experiment_kind']='existing object namespace access checks; no profile admission'
    if crypto:result['experiment_kind']='scoped subject crypto-device setup/startup/revocation only; no full worker admission'
    if crypto_full:result['experiment_kind']=str(size)+'MiB ordinary worker controls with scoped crypto exception; no full product qualification'
    if interactive_ui:result['interactive_scope']=expected['interactive_scope']
    if controller_stop_proof:result['experiment_kind']='Predeclared controller-stop fault injection against one owned Python wait child;no native product build/test or qualification'
    if station_matrix:result['experiment_kind']='Six fixed trusted standard-user station bootstrap comparisons only;no worker/product admission'
    if object_trace:result['experiment_kind']='Bounded owned-child object API trace with original primitive controls;no namespace grant or worker/product admission'
    if native:result['experiment_kind']='representative32MiB restricted x64 compiler/store-helper journey; no full composition/product qualification'
    if native_memory:result['experiment_kind']='Exact production x64 memory-budget component compile/launch in32MiB;not product qualification'
    if full_native:
        result['experiment_kind']='Current exact-source x64 native campaign in proven512MiB ordinary guest; final W105 review remains separate'
        proof=result.get('guest',{}).get('proof') or {}
        result['template_native_product_tests_run']=result.get('native_product_tests_run',False)
        result['native_product_tests_run']=bool(proof.get('tests') or proof.get('diagnostics') or
            any(row.get('label','').startswith('test-') for row in proof.get('commands',[])))
        result['native_product_build_run']=any(row['label']=='build' for row in proof.get('commands',[]))
        if (stage/'retained.tar.xz').exists():
            digest=hashlib.sha256((stage/'retained.tar.xz').read_bytes()).hexdigest()
            if digest!=result.get('guest',{}).get('proof',{}).get('archive_sha256'):raise ValueError('Transferred archive hash mismatch')
            shutil.copyfile(stage/'retained.tar.xz',HERE/'retained.tar.xz')
    result['host_error_tail']=call.stderr[-16384:].decode(errors='replace')
    (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    if station_matrix:
        rows=proof.get('station_bootstrap_matrix',[])
        if len(rows)!=6 or not proof.get('all_owned_processes_retired') or not all(
                row.get('station_retirement',{}).get('retired') and
                row.get('job_retirement',{}).get('active_processes')==0 for row in rows):
            raise RuntimeError('Preserve matrix journal: station/process retirement not established')
    if crypto and not station_matrix and not proof.get('crypto_device_retired'):
        raise RuntimeError('Preserve guest actor journal: crypto-device exception retirement not established')
    if interactive_ui and not station_matrix and not object_trace and not proof.get('object_namespace_retired'):
        raise RuntimeError('Preserve guest actor journal: object namespace retirement not established')
    if full_native and not proof.get('null_device_retired'):
        raise RuntimeError('Preserve guest actor journal: null-sink exception retirement not established')
    if forensic:
        proof=result.get('guest',{}).get('proof',{})
        if not all(proof.get(name) for name in ('image_registry_removed','diagnostic_image_removed','original_runtime_preserved')):
            raise RuntimeError('Preserve guest actor journal: loader image/registry cleanup not established')
    if result.get('guest',{}).get('setup',{}).get('image_removed'):
        cleaned=subprocess.run(['pwsh','-NoProfile','-File',str(stage/'clean-proof.ps1'),'-SizeMiB',str(size)],cwd=ROOT,capture_output=True,timeout=60)
        if cleaned.returncode:
            (HERE/'cleanup-error.txt').write_bytes((cleaned.stdout+cleaned.stderr)[-16384:]);raise RuntimeError('Owned guest cleanup needs review')
        shutil.copyfile(stage/'cleanups.json',HERE/'cleanup.json')
    else:raise RuntimeError('Inspect owned account/image state before another attempt')
    return 0 if result['status']=='pass' and call.returncode==0 else 1

if __name__=='__main__':
    try: code=main()
    except Exception:
        (HERE/'runner-error.txt').write_text(traceback.format_exc()[-16384:],encoding='utf-8',newline='\n')
        raise
    raise SystemExit(code)
