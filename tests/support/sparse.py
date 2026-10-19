"""Size a fresh ordinary fixture without allocating its zero-filled holes."""
import os
import stat


def size_empty_file(stream, size):
    if type(size) is not int or not 0 <= size <= (1 << 63) - 1:
        raise ValueError('Fixture length must be a nonnegative signed-64 integer')
    stream.flush()
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_size:
        raise ValueError('Sparse sizing requires an empty ordinary fixture')
    if os.name == 'nt':
        import ctypes as C
        from ctypes import wintypes as T
        import msvcrt
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.DeviceIoControl.argtypes = [T.HANDLE, T.DWORD, T.LPVOID, T.DWORD,
                                          T.LPVOID, T.DWORD, C.POINTER(T.DWORD), T.LPVOID]
        kernel.DeviceIoControl.restype = T.BOOL
        kernel.SetFilePointerEx.argtypes = [T.HANDLE, C.c_longlong, T.LPVOID, T.DWORD]
        kernel.SetFilePointerEx.restype = T.BOOL
        kernel.SetEndOfFile.argtypes = [T.HANDLE]
        kernel.SetEndOfFile.restype = T.BOOL
        handle = msvcrt.get_osfhandle(stream.fileno())
        returned = T.DWORD()
        if not kernel.DeviceIoControl(handle, 0x000900c4, None, 0, None, 0, C.byref(returned), None):
            raise C.WinError(C.get_last_error())
        if not kernel.SetFilePointerEx(handle, size, None, 0) or not kernel.SetEndOfFile(handle):
            raise C.WinError(C.get_last_error())
    else:
        stream.truncate(size)
    stream.seek(0)
