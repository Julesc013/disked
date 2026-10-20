"""Unprivileged job configuration controls;no storage or child launch."""
import ctypes
import importlib.util
import os
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('explicit_job_workspace',Path(__file__).resolve().parents[2]/'tools/workspace.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class JobLimitTests(unittest.TestCase):
    def test_invalid_limits_refuse_before_any_native_object(self):
        for value in (True,0,1048575,1073741825):
            with self.subTest(memory=value),self.assertRaises(ValueError):S.WindowsJob(memory_bytes=value)
        for value in (True,0,65):
            with self.subTest(processes=value),self.assertRaises(ValueError):S.WindowsJob(process_limit=value)
    @unittest.skipUnless(os.name=='nt','Windows job metadata')
    def test_explicit_limits_and_unchanged_default_round_trip(self):
        for memory,processes in ((None,None),(268435456,8)):
            job=S.WindowsJob(memory_bytes=memory,process_limit=processes)
            try:
                from ctypes import wintypes as T
                query=job.api.QueryInformationJobObject
                query.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.c_void_p];query.restype=T.BOOL
                info=job.limit_info_type();self.assertTrue(query(job.handle,9,ctypes.byref(info),ctypes.sizeof(info),None))
                self.assertEqual(info.basic.flags,0x2000 if memory is None else 0x2208)
                self.assertEqual(info.job_memory,memory or 0);self.assertEqual(info.basic.active,processes or 0)
            finally:job.close()


if __name__=='__main__':unittest.main()
