"""Native shared request/discovery rules and GUI/TUI delivery-state regressions."""
import argparse
import json
from pathlib import Path
import subprocess
import unittest


def invoke(probe, events):
    payload = b"".join(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n" for event in events)
    result = subprocess.run([str(probe)], input=payload, capture_output=True, timeout=15)
    if result.returncode or result.stderr:
        raise AssertionError((result.returncode, result.stderr.decode("utf-8")))
    values = [json.loads(line) for line in result.stdout.splitlines()]
    if len(values) != len(events):
        raise AssertionError((len(values), len(events)))
    return values


def deferred(kind):
    return ([dict(op="synthetic", deferred=True)] if kind == "gui" else [dict(op="defer")]) + [
        dict(op="stage", command="target.list", parameters={}),
        dict(op="review") if kind == "gui" else dict(op="key", key="f9"),
        dict(op="submit") if kind == "gui" else dict(op="key", key="f9"),
    ]


class SharedPresentation(unittest.TestCase):
    def frontends(self):
        return (("gui", ARGS.gui), ("tui", ARGS.tui))

    def test_native_rule_matrix(self):
        result = subprocess.run([str(ARGS.rules)], capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value["passed"])
        names = value["cases"]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(34, len(names))
        self.assertTrue({"maximum-view-equality", "request-id-number", "duplicate-delivery",
                         "old-delivery-cannot-clear-new-request", "callback-error-preserves-slot-and-output",
                         "availability-duplicate-identity", "availability-compatible-background"} <= set(names))

    def test_invalid_identity_preserves_request_and_current_view(self):
        for kind, probe in self.frontends():
            for invalid in (None, False, 1, {}, [], "", "different", "other:1"):
                with self.subTest(kind=kind, invalid=invalid):
                    values = invoke(probe, deferred(kind) + [dict(op="resolve", request_id=invalid),
                                                            dict(op="peek"), dict(op="resolve")])
                    before, error, after, completed = values[-4:]
                    self.assertEqual("frontend_completion_identity", error["error"])
                    self.assertEqual(before["state"], after["state"])
                    self.assertEqual(kind + ":1", after["state"]["pending_request"])
                    self.assertEqual("", completed["state"]["pending_request"])
                    self.assertEqual(kind + ":1", completed["state"]["last_outcome"]["request_id"])
                    self.assertIsNone(completed["state"]["earlier_request"])

    def test_missing_identity_preserves_request(self):
        for kind, probe in self.frontends():
            with self.subTest(kind=kind):
                values = invoke(probe, deferred(kind) + [dict(op="resolve", omit_request_id=True),
                                                        dict(op="peek"), dict(op="resolve")])
                self.assertEqual("frontend_completion_identity", values[-3]["error"])
                self.assertEqual(values[-4]["state"], values[-2]["state"])
                self.assertEqual(kind + ":1", values[-1]["state"]["last_outcome"]["request_id"])

    def test_unsolicited_completion_changes_no_view(self):
        for kind, probe in self.frontends():
            with self.subTest(kind=kind):
                before, error, after = invoke(probe, [dict(op="peek"), dict(op="resolve"), dict(op="peek")])
                self.assertEqual("frontend_completion_identity", error["error"])
                self.assertEqual(before["state"], after["state"])

    def test_duplicate_completion_changes_no_view(self):
        for kind, probe in self.frontends():
            with self.subTest(kind=kind):
                values = invoke(probe, deferred(kind) + [dict(op="resolve"), dict(op="resolve"), dict(op="peek")])
                self.assertEqual("frontend_completion_identity", values[-2]["error"])
                self.assertEqual(values[-3]["state"], values[-1]["state"])

    def test_invalid_then_valid_late_completion_keeps_new_observation(self):
        for kind, probe in self.frontends():
            with self.subTest(kind=kind):
                values = invoke(probe, deferred(kind) + [dict(op="publish", remove="fake:alpha@1"),
                    dict(op="observe"), dict(op="resolve", request_id="different"), dict(op="peek"), dict(op="resolve")])
                before, error, retained, completed = values[-4:]
                self.assertEqual("frontend_completion_identity", error["error"])
                self.assertEqual(before["state"], retained["state"])
                self.assertEqual(before["state"]["last_outcome"], completed["state"]["last_outcome"])
                self.assertEqual(before["state"]["view_revision"], completed["state"]["view_revision"])
                self.assertEqual(kind + ":1", completed["state"]["earlier_request"]["request_id"])
                self.assertEqual("", completed["state"]["pending_request"])

    def test_old_completion_does_not_replace_new_command_outcome(self):
        for kind, probe in self.frontends():
            with self.subTest(kind=kind):
                next_command = [dict(op="stage", command="target.list", parameters={}),
                    dict(op="review") if kind == "gui" else dict(op="key", key="f9"),
                    dict(op="submit") if kind == "gui" else dict(op="key", key="f9")]
                values = invoke(probe, deferred(kind) + next_command + [dict(op="resolve"), dict(op="resolve"), dict(op="peek")])
                current, earlier, duplicate, final = values[-4:]
                self.assertEqual(kind + ":2", current["state"]["last_outcome"]["request_id"])
                self.assertEqual(current["state"]["last_outcome"], earlier["state"]["last_outcome"])
                self.assertEqual(kind + ":1", earlier["state"]["earlier_request"]["request_id"])
                self.assertEqual("frontend_completion_identity", duplicate["error"])
                self.assertEqual(earlier["state"], final["state"])

    def test_both_models_refuse_transport_session_and_planned_commands(self):
        for kind, probe in self.frontends():
            for command in ("protocol.serve", "shell.open", "shell.close", "partition.resize.plan"):
                with self.subTest(kind=kind, command=command):
                    value = invoke(probe, [dict(op="stage", command=command, parameters={})])[0]["state"]
                    self.assertEqual("command_unavailable", value["last_outcome"]["diagnostics"][0]["code"])
                    self.assertEqual("0", value["requests"])
                    self.assertEqual("", value["pending_request"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", type=Path, required=True)
    parser.add_argument("--tui", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    ARGS = parser.parse_args()
    unittest.main(argv=[__file__], verbosity=2)
