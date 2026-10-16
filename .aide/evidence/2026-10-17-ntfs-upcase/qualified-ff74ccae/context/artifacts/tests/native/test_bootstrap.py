"""Real process acceptance for DE-W010; only temporary ordinary files are used."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


HELP = (
    "DiskEd native bootstrap (fake-only; human output only)\n"
    "Usage: disked build inspect | command list | commands | help [command]\n"
    "Static help: --help or -h before, between or after command words.\n"
    "Storage, GUI, TUI, shell and machine output are unavailable.\n"
)


class NativeBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = read(ARGS.root / "spec/catalog/native-bootstrap.json")
        cls.commands = read(ARGS.root / "spec/catalog/commands.json")["commands"]
        cls.identity = read(ARGS.identity)

    def launch(self, argv):
        with tempfile.TemporaryDirectory(prefix="disked-native-") as directory:
            root = Path(directory)
            # No repository, installed product or toolchain on the process PATH.
            env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
            env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"), TEMP=directory, TMP=directory)
            result = subprocess.run([str(ARGS.exe), *argv], cwd=root, env=env,
                stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
            self.assertEqual([], list(root.iterdir()), "Application created files")
            self.assertNotEqual(97, result.returncode, "Essential command initialized the poison provider")
            stdout = result.stdout.decode("ascii").replace("\r\n", "\n")
            stderr = result.stderr.decode("ascii").replace("\r\n", "\n")
            self.assertNotIn("\x1b", stdout + stderr)
            return result.returncode, stdout, stderr

    def assert_case(self, case):
        status, out, err = self.launch(case["argv"])
        if "error" in case:
            code = case["error"]
            expected = self.profile["diagnostics"][code]
            self.assertEqual(expected["exit"], status)
            self.assertEqual("", out)
            self.assertEqual(f"disked: {code}: {expected['message']}\n", err)
            return
        self.assertEqual(0, status)
        self.assertEqual("", err)
        if case["output"] == "help":
            self.assertEqual(HELP, out)
        elif case["output"] == "build":
            rows = out.splitlines()
            values = dict(row.split("=", 1) for row in rows)
            expected = dict(self.identity["identity"], fake_provider=self.profile["fake_provider_id"])
            self.assertEqual(len(expected), len(rows))
            self.assertEqual(expected, values)
        elif case["output"] == "commands":
            expected = "id\tcontract_status\timplementation_status\tavailability\treason\tcommand\n"
            for command in self.commands:
                implemented = command["id"] in self.profile["implemented_commands"]
                fields = [command["id"], command["availability"], "implemented" if implemented else "planned",
                    "available" if implemented else "unavailable", "bootstrap_human_only" if implemented else "not_implemented", " ".join(command["words"])]
                expected += "\t".join(fields) + "\n"
            self.assertEqual(expected, out)
        elif case["output"] == "command-help":
            command = next(c for c in self.commands if c["id"] == case["command"])
            availability = "available (bootstrap human subset)" if command["id"] in self.profile["implemented_commands"] else "unavailable (planned)"
            self.assertEqual(f"{command['id']}: {command['summary']}\ncommand: {' '.join(command['words'])}\navailability: {availability}\n", out)
        else:
            self.fail("Unknown expected-output kind")

    def test_predefined_cases(self):
        for case in read(ARGS.root / "spec/fixtures/native-bootstrap.json")["cases"]:
            with self.subTest(case=case["id"]):
                self.assert_case(case)

    def test_every_registered_spelling_and_static_help(self):
        for command in self.commands:
            for words in [command["words"], *(alias.split() for alias in command["aliases"])]:
                with self.subTest(command=command["id"], words=words):
                    self.assert_case(dict(argv=[*words, "--help"], output="command-help", command=command["id"]))
                    if command["id"] not in self.profile["implemented_commands"]:
                        self.assert_case(dict(argv=words, error="command_unavailable"))

    def test_tokens_are_not_retokenized_or_echoed(self):
        for argv in [["build inspect"], ["command list"], ["\x1b[31m--help"], ["a" * 8000]]:
            with self.subTest(argv=argv[:1]):
                self.assert_case(dict(argv=argv, error="command_unavailable"))

    def test_source_identity_matches_actual_inputs(self):
        expected = {name: digest((ARGS.root / name).read_bytes())
            for name in sorted(read(ARGS.root / "tools/build-inputs.json")["files"])}
        self.assertEqual(expected, self.identity["inputs"])
        self.assertEqual(digest(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()),
            self.identity["identity"]["input_digest"])
        self.assertEqual(subprocess.check_output(["git", "-C", str(ARGS.root), "rev-parse", "HEAD"], text=True).strip(),
            self.identity["identity"]["source_revision"])
        self.assertEqual("DiskEd", self.identity["identity"]["product"])
        self.assertEqual("windows.nt10.x64.win32", self.identity["identity"]["target"])
        self.assertEqual("Release", self.identity["identity"]["configuration"])
        self.assertEqual(digest(json.dumps(self.identity['build_settings'], sort_keys=True, separators=(',', ':')).encode()),
            self.identity['identity']['configuration_digest'])

    def test_broken_stdout_is_not_success(self):
        # On Windows, a closed pipe must not become a successful result.
        with tempfile.TemporaryDirectory(prefix="disked-pipe-") as directory:
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                result = subprocess.run([str(ARGS.exe), "build", "inspect"], cwd=directory,
                    stdin=subprocess.DEVNULL, stdout=write_fd, stderr=subprocess.PIPE, timeout=10)
            finally:
                os.close(write_fd)
            self.assertEqual(4, result.returncode)
            self.assertEqual(b"disked: output_error: unable to write output\r\n", result.stderr)
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_pe_architecture_imports_and_security_flags(self):
        dumpbin = Path(self.identity['compiler_path']).with_name('dumpbin.exe')
        headers = subprocess.check_output([str(dumpbin), '/HEADERS', str(ARGS.exe)], text=True, timeout=15)
        for expected in ['8664 machine (x64)', 'magic # (PE32+)', '10.00 subsystem version',
                         'subsystem (Windows CUI)', 'Dynamic base', 'NX compatible', 'Control Flow Guard']:
            self.assertIn(expected, headers)
        dependencies = subprocess.check_output([str(dumpbin), '/DEPENDENTS', str(ARGS.exe)], text=True, timeout=15)
        imported = re.findall(r'^\s+([A-Za-z0-9_.-]+\.dll)\s*$', dependencies, re.MULTILINE | re.IGNORECASE)
        composition = next(c for c in read(ARGS.root/'spec/catalog/compositions.json')['compositions']
            if c['id'] == self.profile['composition_id'])
        self.assertEqual(['kernel32.dll'], sorted(name.lower() for name in imported))
        self.assertEqual(sorted(name.lower() for name in composition['mandatory_loader_dependencies']),
            sorted(name.lower() for name in imported))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("exe", "root", "identity"):
        parser.add_argument("--" + name, type=Path, required=True)
    ARGS = parser.parse_args()
    ARGS.exe = ARGS.exe.resolve()
    ARGS.root = ARGS.root.resolve()
    unittest.main(argv=[__file__], verbosity=2)
