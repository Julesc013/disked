"""Temporary fixtures that retain an AppContainer's private parent permissions."""
import ctypes
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import weakref

SOURCE = Path(__file__).resolve().parents[2]


def _is_appcontainer():
    if os.name != 'nt':
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    security = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.GetCurrentProcess.restype = T.HANDLE
    kernel.CloseHandle.argtypes = [T.HANDLE]
    security.OpenProcessToken.argtypes = [T.HANDLE, T.DWORD, ctypes.POINTER(T.HANDLE)]
    security.GetTokenInformation.argtypes = [T.HANDLE, ctypes.c_int, ctypes.c_void_p, T.DWORD, ctypes.POINTER(T.DWORD)]
    token, size, container = T.HANDLE(), T.DWORD(), T.DWORD()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not security.GetTokenInformation(token, 29, ctypes.byref(container), 4, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(container.value)
    finally:
        kernel.CloseHandle(token)


def _plain(path):
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if item.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked fixture directory ancestor')


def _remove(path, identity):
    _plain(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (info.st_dev, info.st_ino) != identity or not path.is_dir():
        raise ValueError('Fixture directory identity changed; preserved')
    # Python's rmtree removes directory junctions themselves, not their targets.
    # Never repair another directory's permissions to make cleanup succeed.
    shutil.rmtree(path)


class _InheritedDirectory:
    def __init__(self, parent, prefix):
        for _ in range(32):
            path = parent / (prefix + uuid.uuid4().hex)
            try:
                # The containing worker workspace already has private user /
                # package ACLs. 0700 on Windows instead installs a protected
                # owner/admin DACL that omits the package identity.
                path.mkdir(mode=0o777)
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError('Fixture directory collision limit reached')
        info = path.lstat()
        self.name = str(path)
        self._identity = (info.st_dev, info.st_ino)
        self._finalizer = weakref.finalize(self, _remove, path, self._identity)

    def __enter__(self):
        return self.name

    def __exit__(self, *unused):
        self.cleanup()

    def cleanup(self):
        self._finalizer.detach()
        _remove(Path(self.name), self._identity)


def fixture_parent():
    """Resolve TEMP only when it belongs to this source's managed workspace."""
    value = os.environ.get('DISKED_WORK_ROOT')
    if not value:
        raise ValueError('Owned managed workspace required')
    work, parent = Path(value).absolute(), Path(tempfile.gettempdir()).absolute()
    _plain(work)
    _plain(parent)
    work, parent = work.resolve(), parent.resolve()
    if not parent.is_relative_to(work):
        raise ValueError('Fixture parent is outside the owned workspace')
    marker = work / 'owner.json'
    _plain(marker)
    if marker.stat().st_size > 4096:
        raise ValueError('Oversized fixture workspace marker')
    owner = json.loads(marker.read_bytes())
    if Path(owner['root']).resolve() != SOURCE:
        raise ValueError('Fixture workspace belongs to another source')
    return parent


def _check_prefix(prefix):
    if not isinstance(prefix, str) or not prefix or any(c in prefix for c in '\\/:\0'):
        raise ValueError('Fixture prefix must be a nonempty basename')


def managed_directory(*, prefix):
    """Require owned managed scratch for either an ordinary or confined token."""
    _check_prefix(prefix)
    parent = fixture_parent()
    if _is_appcontainer():
        return _InheritedDirectory(parent, prefix)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=parent)


def temporary_directory(*, prefix):
    """Preserve ordinary tempfile behavior; verify confined inherited fixtures."""
    if not _is_appcontainer():
        return tempfile.TemporaryDirectory(prefix=prefix)
    _check_prefix(prefix)
    parent = fixture_parent()
    return _InheritedDirectory(parent, prefix)
