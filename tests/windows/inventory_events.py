"""Four owned private test events; no foreground input or global setting."""
import ctypes as c
from ctypes import wintypes as w
import uuid

k=c.WinDLL('kernel32',use_last_error=True)
k.CreateEventW.argtypes=[c.c_void_p,w.BOOL,w.BOOL,w.LPCWSTR];k.CreateEventW.restype=w.HANDLE
k.SetEvent.argtypes=[w.HANDLE];k.SetEvent.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL

class InventoryEvents:
    def __init__(self):
        self.handles={};self.names={};nonce=uuid.uuid4().hex
        try:
            for action in ('advance','release','cancel','timeout'):
                name='Local\\DiskEd.Inventory.'+nonce+'.'+action
                handle=k.CreateEventW(None,False,False,name)
                error=c.get_last_error()
                if not handle:raise OSError(error,'owned inventory event')
                if error==183:
                    k.CloseHandle(handle)
                    raise OSError(error,'owned inventory event already exists')
                self.handles[action]=handle;self.names[action]=name
        except BaseException:self.close();raise
    def signal(self,action):
        if not k.SetEvent(self.handles[action]):raise OSError(c.get_last_error(),'inventory event signal')
    def close(self):
        for handle in self.handles.values():k.CloseHandle(handle)
        self.handles={}
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
