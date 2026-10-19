"""Owned capped breadcrumbs before optional native imports; no ctypes at entry."""
import os
import sys

name=sys.argv[1]
if name not in ('loader-standard.log','loader-restricted.log','loader-detached.log'):
    raise ValueError('Fixed owned observation basename required')

with open(name,'x',encoding='utf-8',newline='\n') as output:
    def mark(text):
        output.write(text+'\n');output.flush();os.fsync(output.fileno())
    mark('python_entered')
    for name in ('json','pathlib','subprocess','tempfile','ctypes','ctypes.wintypes'):
        mark('before_import '+name)
        try:__import__(name)
        except BaseException as error:
            mark('import_error '+type(error).__name__+' '+str(error));raise
        mark('after_import '+name)
    import ctypes
    for name in ('user32','shell32'):
        mark('before_load '+name)
        try:ctypes.WinDLL(name,use_last_error=True)
        except BaseException as error:
            mark('load_error '+type(error).__name__+' '+str(error));raise
        mark('after_load '+name)
    mark('complete')
