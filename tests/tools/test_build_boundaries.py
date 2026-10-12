"""Negative fixtures for the generated-build/header boundary checker."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[2] / "tools/check-build-boundaries.py"
SPEC = importlib.util.spec_from_file_location("disked_build_boundaries", MODULE_PATH)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.build = self.root / "build"
        self.build.mkdir()
        self.flags = ["/W4", "/WX", "/MT"]
        self.contract = {
            "core_targets": {"json": {"sources": ["source/runtime/command/json.cpp"], "build_closure": []}},
            "required_compile_flags": self.flags,
            "isolated_consumers": {"json_probe": ["command", "invocation"]},
        }
        self.write("source/runtime/command/json.h", "#pragma once\n")
        self.write("source/runtime/command/json.cpp", '#include "json.h"\n')
        self.write("tests/native/json_probe.cpp", '#include "json.h"\n')
        self.targets = [self.target("json", "source/runtime/command/json.cpp"),
                        self.target("json_probe", "tests/native/json_probe.cpp", ["json"])]

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def target(self, name, source, dependencies=()):
        return {
            "id": name, "name": name, "type": "STATIC_LIBRARY",
            "sources": [{"path": source, "compileGroupIndex": 0}],
            "dependencies": [{"id": value} for value in dependencies],
            "compileGroups": [{"language": "CXX", "languageStandard": {"standard": "14"},
                               "compileCommandFragments": [{"fragment": " ".join(self.flags)}],
                               "includes": [{"path": str(self.root / "source/runtime/command")}]}],
        }

    def inspect(self):
        return CHECKER.inspect(self.root, self.build, self.targets, self.contract)

    def fails(self, text):
        result = self.inspect()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(text in message for message in result["violations"]), result["violations"])

    def test_valid_generated_graph_and_header_resolution(self):
        result = self.inspect()
        self.assertEqual(result["status"], "PASS", result["violations"])
        self.assertEqual(result["quoted_include_edges"], 2)

    def test_json_cannot_absorb_command_implementation(self):
        self.write("source/runtime/command/command.cpp", "")
        self.targets[0]["sources"].append({"path": "source/runtime/command/command.cpp", "compileGroupIndex": 0})
        self.fails("unexpected compiled sources")

    def test_transitive_consumer_contamination(self):
        self.write("source/runtime/command/command.cpp", "")
        self.targets.append(self.target("command", "source/runtime/command/command.cpp"))
        self.targets[0]["dependencies"].append({"id": "command"})
        self.fails("json_probe: unwanted build dependency command")

    def test_runtime_cannot_include_provider(self):
        self.write("source/providers/image/file.h", "#pragma once\n")
        self.write("source/runtime/command/json.cpp", '#include "../../providers/image/file.h"\n')
        self.fails("forbidden include")

    def test_runtime_cannot_depend_on_provider(self):
        self.write("source/providers/image/file.cpp", "")
        self.targets.append(self.target("image", "source/providers/image/file.cpp"))
        self.targets[0]["dependencies"].append({"id": "image"})
        self.fails("forbidden build dependency image")

    def test_portable_cannot_depend_on_runtime(self):
        self.write("source/portable/hash/hash.cpp", "")
        self.targets.append(self.target("hash", "source/portable/hash/hash.cpp", ["json"]))
        self.fails("hash: forbidden build dependency json")

    def test_frontend_model_cannot_depend_on_provider(self):
        self.write("source/providers/image/file.cpp", "")
        self.write("source/apps/disked/tui/tui_model.cpp", "")
        self.targets.extend([self.target("image", "source/providers/image/file.cpp"),
                             self.target("tui", "source/apps/disked/tui/tui_model.cpp", ["image"])])
        self.fails("tui: forbidden build dependency image")

    def test_missing_header(self):
        self.write("source/runtime/command/json.cpp", '#include "missing.h"\n')
        self.fails("unresolved")

    def test_ambiguous_header_even_if_compiler_would_pick_first(self):
        self.write("source/runtime/command/json.cpp", '#include "shared.h"\n')
        for folder in ("source/runtime/command", "source/runtime/presentation"):
            self.write(folder + "/shared.h", "#pragma once\n")
        self.targets[0]["compileGroups"][0]["includes"].append({"path": str(self.root / "source/runtime/presentation")})
        self.fails("ambiguous")

    def test_wrong_case_does_not_qualify_portable_header_spelling(self):
        self.write("source/runtime/command/json.cpp", '#include "JSON.h"\n')
        self.fails("include case" if (self.root / "source/runtime/command/JSON.h").is_file() else "unresolved")

    def test_weakened_compiler_options(self):
        self.targets[0]["compileGroups"][0]["compileCommandFragments"] = [{"fragment": "/W4 /MT"}]
        self.fails("missing compile option /WX")

    def test_equivalent_msvc_dash_options(self):
        self.targets[0]["compileGroups"][0]["compileCommandFragments"] = [{"fragment": "-W4 -WX -MT"}]
        self.assertEqual(self.inspect()["status"], "PASS")

    def test_dynamic_crt_does_not_satisfy_static_crt(self):
        self.targets[0]["compileGroups"][0]["compileCommandFragments"] = [{"fragment": "/W4 /WX -MD"}]
        self.fails("missing compile option /MT")

    def test_mixed_library_cannot_bypass_layer_check(self):
        self.write("source/providers/image/file.cpp", "")
        self.targets[0]["sources"].append({"path": "source/providers/image/file.cpp", "compileGroupIndex": 0})
        self.fails("mixed ownership")

    def test_unresolved_build_dependency(self):
        self.targets[0]["dependencies"].append({"id": "missing"})
        self.fails("missing dependency missing")

    def test_file_api_reply_must_belong_to_checkout(self):
        reply = self.build / ".cmake/api/v1/reply"
        reply.mkdir(parents=True)
        model = {"paths": {"source": str(self.root / "other"), "build": str(self.build)}, "configurations": []}
        (reply / "codemodel.json").write_text(json.dumps(model), encoding="utf-8")
        index = {"objects": [{"kind": "codemodel", "version": {"major": 2}, "jsonFile": "codemodel.json"}]}
        (reply / "index-fixture.json").write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different source"):
            CHECKER.load_codemodel(self.root, self.build, "Release")


if __name__ == "__main__":
    unittest.main()
