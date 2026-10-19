"""Tiny ordinary-file checks for byte-exact, bounded fixture allocation."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fixture_sparse', ROOT / 'tests/support/sparse.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class SparseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='disked-small-sparse-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'owned.img'

    def test_exact_holes_regions_length_and_small_allocation(self):
        size, unit = 8 * 1024 * 1024, 65536
        with self.path.open('x+b') as stream:
            S.size_empty_file(stream, size)
            stream.write(b'A' * 16)
            stream.seek(size - 16)
            stream.write(b'B' * 16)
            stream.flush()
            if os.name == 'nt':
                import msvcrt
                class Standard(C.Structure):
                    _fields_ = [('allocated', C.c_longlong), ('end', C.c_longlong),
                                ('links', T.DWORD), ('pending', C.c_byte), ('directory', C.c_byte)]
                kernel = C.WinDLL('kernel32', use_last_error=True)
                query = kernel.GetFileInformationByHandleEx
                query.argtypes = [T.HANDLE, C.c_int, T.LPVOID, T.DWORD]
                query.restype = T.BOOL
                info = Standard()
                if not query(msvcrt.get_osfhandle(stream.fileno()), 1, C.byref(info), C.sizeof(info)):
                    raise C.WinError(C.get_last_error())
                allocated = info.allocated
            else:
                allocated = os.fstat(stream.fileno()).st_blocks * 512
            self.assertLessEqual(allocated, 2 * unit)
        self.assertEqual(self.path.stat().st_size, size)
        expected, actual = hashlib.sha256(), hashlib.sha256()
        expected.update(b'A' * 16 + bytes(unit - 16))
        for _ in range(size // unit - 2):
            expected.update(bytes(unit))
        expected.update(bytes(unit - 16) + b'B' * 16)
        with self.path.open('rb') as stream:
            while block := stream.read(unit):
                actual.update(block)
        self.assertEqual(actual.digest(), expected.digest())

    def test_nonempty_input_refused_without_changing_bytes(self):
        with self.path.open('x+b') as stream:
            stream.write(b'preserve')
            with self.assertRaisesRegex(ValueError, 'empty ordinary'):
                S.size_empty_file(stream, 1024)
        self.assertEqual(self.path.read_bytes(), b'preserve')

    def test_invalid_lengths_refused_before_sizing(self):
        with self.path.open('x+b') as stream:
            for size in (-1, True, 1.5, 1 << 63):
                with self.subTest(size=size), self.assertRaises(ValueError):
                    S.size_empty_file(stream, size)
            self.assertEqual(os.fstat(stream.fileno()).st_size, 0)


if __name__ == '__main__':
    unittest.main()
