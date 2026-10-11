"""Bounded capture of the test-owned console; no foreground input."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tests/frontend"))
from console_tui_fixture import k,w,c,checked,configure,key,snapshot,active,info,Coord

def current_text():
 handle=active()
 try:
  value=info(handle);count=min(value.size.X*max(value.cursor.Y+1,value.window.Bottom+1),262144)
  buffer=c.create_unicode_buffer(count+1);got=w.DWORD();checked(k.ReadConsoleOutputCharacterW(handle,buffer,count,Coord(0,0),c.byref(got)))
  return '\n'.join(buffer[i:min(i+value.size.X,got.value)].rstrip() for i in range(0,got.value,value.size.X))
 finally:k.CloseHandle(handle)
