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
        return CHECKER.inspect(self.root, self.build, self.targets, self.contract, getattr(self, "usage", None))

    def qualified_fixture(self):
        self.contract["qualified_includes"] = True
        self.contract["compile_only_include_guards"] = ["DISKED_FIXTURE_GUARD"]
        header = "source/runtime/command/json.h"
        self.targets[0]["sources"].append({"path": header})
        self.usage = {"schema": "org.disked.private-header-usage/1", "targets": {
            "json": {"headers": [header], "interface_headers": [header], "direct": [], "interface": []},
            "json_probe": {"headers": [], "interface_headers": [], "direct": ["json"], "interface": []},
        }}
        for target in self.targets:
            target["compileGroups"][0]["includes"] = [{"path": str(self.root / "source")}]
        self.write("tests/native/json_probe.cpp", '#include "runtime/command/json.h"\n')

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

    def c90_fixture(self):
        self.contract["core_targets"]["json"].update(
            language_standard="90", required_compile_flags=["/W4", "/WX", "/GS", "/MT"])
        group = self.targets[0]["compileGroups"][0]
        group["language"] = "C"
        group["languageStandard"]["standard"] = "90"
        group["compileCommandFragments"] = [{"fragment": "/W4 /WX /GS /MT"}]

    def test_per_target_c90_contract(self):
        self.c90_fixture()
        self.assertEqual(self.inspect()["status"], "PASS")

    def test_per_target_standard_cannot_be_changed(self):
        self.c90_fixture()
        self.targets[0]["compileGroups"][0]["languageStandard"]["standard"] = "99"
        self.fails("language standard 90")

    def test_per_target_options_cannot_be_weakened(self):
        self.c90_fixture()
        self.targets[0]["compileGroups"][0]["compileCommandFragments"] = [{"fragment": "/W4 /WX /MT"}]
        self.fails("missing compile option /GS")

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

    def test_qualified_header_visibility(self):
        self.qualified_fixture()
        self.assertEqual(self.inspect()["status"], "PASS")

    def test_bare_cross_module_header_is_rejected_even_if_it_resolves(self):
        self.qualified_fixture()
        self.write("tests/native/json_probe.cpp", '#include "json.h"\n')
        self.targets[1]["compileGroups"][0]["includes"].append({"path": str(self.root / "source/runtime/command")})
        self.fails("unqualified cross-module include")

    def test_build_dependency_does_not_supply_compile_visibility(self):
        self.qualified_fixture()
        self.usage["targets"]["json_probe"]["direct"] = []
        self.fails("undeclared header dependency")

    def test_private_link_does_not_leak_headers_to_consumer(self):
        self.qualified_fixture()
        self.write("source/runtime/presentation/bridge.cpp", "")
        self.targets.append(self.target("bridge", "source/runtime/presentation/bridge.cpp", ["json"]))
        self.targets[1]["dependencies"] = [{"id": "bridge"}]
        self.usage["targets"]["json_probe"]["direct"] = ["bridge"]
        self.usage["targets"]["bridge"] = dict(headers=[], interface_headers=[], direct=["json"], interface=[])
        self.fails("json_probe: undeclared header dependency")

    def test_public_interface_supplies_transitive_headers(self):
        self.qualified_fixture()
        self.write("source/runtime/presentation/bridge.cpp", "")
        self.targets.append(self.target("bridge", "source/runtime/presentation/bridge.cpp", ["json"]))
        self.targets[1]["dependencies"] = [{"id": "bridge"}]
        self.usage["targets"]["json_probe"]["direct"] = ["bridge"]
        self.usage["targets"]["bridge"] = dict(headers=[], interface_headers=[], direct=["json"], interface=["json"])
        self.assertEqual(self.inspect()["status"], "PASS")

    def test_unexported_header_is_private(self):
        self.qualified_fixture()
        self.usage["targets"]["json"]["interface_headers"] = []
        self.fails("json_probe: undeclared header dependency")

    def test_header_ownership_requires_codemodel_source(self):
        self.qualified_fixture()
        self.targets[0]["sources"].pop()
        self.fails("header ownership absent from codemodel sources")

    def test_exported_header_requires_owner(self):
        self.qualified_fixture()
        self.usage["targets"]["json"]["headers"] = []
        self.fails("exported header has no owning source")

    def test_projection_cannot_be_missing(self):
        self.qualified_fixture()
        self.usage = None
        self.fails("Missing current CMake private header-usage projection")

    def test_unknown_usage_target_refuses(self):
        self.qualified_fixture()
        self.usage["targets"]["json_probe"]["direct"] = ["missing"]
        self.fails("unknown compile-usage dependency")

    def test_compile_only_false_guard_does_not_add_dependency(self):
        self.qualified_fixture()
        self.usage["targets"]["json_probe"]["direct"] = []
        self.write("tests/native/json_probe.cpp", '#ifdef DISKED_FIXTURE_GUARD\n#include "runtime/command/json.h"\n#endif\n')
        self.assertEqual(self.inspect()["status"], "PASS")
        self.targets[1]["compileGroups"][0]["defines"] = [{"define": "DISKED_FIXTURE_GUARD=1"}]
        self.fails("undeclared header dependency")

    def test_unknown_guard_stays_conservative(self):
        self.qualified_fixture()
        self.usage["targets"]["json_probe"]["direct"] = []
        self.write("tests/native/json_probe.cpp", '#ifdef DISKED_UNDECLARED_GUARD\n#include "runtime/command/json.h"\n#endif\n')
        self.fails("undeclared header dependency")

    def test_compile_only_guard_cannot_be_redefined(self):
        self.qualified_fixture()
        self.write("tests/native/json_probe.cpp", '#define DISKED_FIXTURE_GUARD 1\n#ifdef DISKED_FIXTURE_GUARD\n#include "runtime/command/json.h"\n#endif\n')
        with self.assertRaisesRegex(ValueError, "redefined in source"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
