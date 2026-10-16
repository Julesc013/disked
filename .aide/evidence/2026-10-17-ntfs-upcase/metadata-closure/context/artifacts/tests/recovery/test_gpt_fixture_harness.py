"""Process diagnostics and retained dependencies for the private GPT fixtures."""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_gpt_restoration import Replies, close, fixture_parent


class FixtureHarnessTests(unittest.TestCase):
    def test_reader_reports_bad_json_and_drains_stderr(self):
        script = "import sys;sys.stderr.buffer.write(b'x'*200000);sys.stderr.flush();print('bad json',flush=True)"
        process = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rows = Replies(process)
        observations = []
        try:
            self.assertIsNone(rows.get(timeout=5))
            self.assertEqual(rows.wait(timeout=5), 0)
            rows.join()
            self.assertEqual(rows.stderr_bytes, 200000)
            self.assertIn('JSONDecodeError', rows.error)
        finally:
            close(process, rows, observations)
        self.assertTrue(observations[-1]['exit_confirmed'])

    def test_timeout_reports_named_phase_without_retiring_child(self):
        script = "import sys;print('{\"phase\":\"prepared\"}',flush=True);sys.stdin.buffer.read()"
        process = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rows = Replies(process)
        observations = []
        try:
            self.assertEqual(rows.get(timeout=5)['phase'], 'prepared')
            with self.assertRaisesRegex(TimeoutError, 'named-execution'):
                rows.get(timeout=0.05, phase='named-execution')
            self.assertIsNone(process.poll())
        finally:
            close(process, rows, observations)
        self.assertTrue(observations[-1]['kill_requested'])
        self.assertTrue(observations[-1]['exit_confirmed'])

    def test_unconfirmed_exit_preserves_original_failure_and_pipes(self):
        class Process:
            pid = 1
            killed = False
            def poll(self): return None
            def kill(self): self.killed = True
            def wait(self, timeout):
                self.timeout = timeout
                raise subprocess.TimeoutExpired('synthetic-owned-fixture', timeout)
        class Output:
            def snapshot(self, phase): return dict(phase=phase, pid=1, exit_code=None)
        process, observations = Process(), []
        original = RuntimeError('original-execution-timeout')
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            try:
                raise original
            except RuntimeError:
                close(process, Output(), observations)
        self.assertTrue(process.killed)
        self.assertEqual(process.timeout, 5)
        self.assertFalse(observations[0]['exit_confirmed'])
        self.assertIn('exit unconfirmed', original.__notes__[0])
        self.assertIn('UNCONFIRMED_RETIREMENT', errors.getvalue())

    def test_failed_fixture_retains_dependencies_and_unconfirmed_cleanup_fails(self):
        with tempfile.TemporaryDirectory(prefix='disked-harness-') as outer:
            root, state = Path(outer), {}
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(AssertionError, 'confirmed process exit'):
                    with fixture_parent(root, state, [dict(exit_confirmed=False)]) as directory:
                        (directory / 'backup.bin').write_bytes(b'retained dependency')
            self.assertTrue(state['retained'])
            self.assertEqual((Path(state['directory']) / 'backup.bin').read_bytes(), b'retained dependency')

    def test_successful_fixture_cleanup_requires_confirmed_exit(self):
        with tempfile.TemporaryDirectory(prefix='disked-harness-') as outer:
            state = {}
            with fixture_parent(Path(outer), state, [dict(exit_confirmed=True)]) as directory:
                (directory / 'backup.bin').write_bytes(b'finished fixture')
            self.assertFalse(state['retained'])
            self.assertFalse(directory.exists())


if __name__ == '__main__':
    unittest.main()
