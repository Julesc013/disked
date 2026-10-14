"""Measure native process creation under the existing read-only directory fence."""
import ctypes as C
import json
import subprocess
from pathlib import Path
root = Path.cwd()
k = C.WinDLL('kernel32', use_last_error=True)
k.CreateFileW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p]
k.CreateFileW.restype = C.c_void_p
k.CloseHandle.argtypes = [C.c_void_p]
cases = []
for folder, program in [
    ('exfat-command-exact-60376a0e/build/Release', 'disked_fat_test.exe'),
    ('exfat-command-exact-60376a0e/launch-probe', 'old_spawn_probe.exe')]:
    directory = root / '.aide-local' / folder
    for pinned in [False, True]:
        handle = None
        try:
            if pinned:
                handle = k.CreateFileW(str(directory), 0x80000000, 1, None, 3, 0x02200000, None)
                assert handle != C.c_void_p(-1).value, C.get_last_error()
            process = subprocess.run([str(directory / program), 'help', '--json'], cwd=directory,
                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            cases.append(dict(directory=str(directory), pinned=pinned, created=True,
                exit_code=process.returncode, stdout_bytes=len(process.stdout), stderr_bytes=len(process.stderr)))
        except OSError as error:
            cases.append(dict(directory=str(directory), pinned=pinned, created=False,
                platform_code=error.winerror, error=str(error)))
        finally:
            if handle: k.CloseHandle(handle)
(root / '.aide-local/exfat-reader-working-directory-probe.json').write_text(
    json.dumps(cases, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(cases, indent=2))
