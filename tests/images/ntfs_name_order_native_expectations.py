"""Independent fixture semantics and retained native observations for DE-W104."""
import copy
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess

import test_ntfs_file as held
from test_ntfs_name_order import JointVolume, canonical, sha

PROBE = FAULT = PURE = OUTPUT = None
RECEIPTS = []
SOURCE_RECEIPTS = []


def invoke(binary, payload, timeout, env=None):
    request = OUTPUT.with_name(OUTPUT.stem + "-request-" + str(len(RECEIPTS)) + ".json")
    request.write_bytes(payload)
    process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env)
    timed_out = False
    try:
        stdout, stderr = process.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    raw = OUTPUT.with_name(OUTPUT.stem + "-response-" + str(len(RECEIPTS)) + ".json")
    error = raw.with_suffix(".stderr")
    raw.write_bytes(stdout)
    error.write_bytes(stderr)
    receipt = dict(command=[str(binary)], input_sha256=sha(payload), output_sha256=sha(stdout),
                   stderr_sha256=sha(stderr), raw_output=str(raw.resolve()),
                   raw_input=str(request.resolve()), raw_stderr=str(error.resolve()), exit_code=process.returncode,
                   process_id=process.pid, timed_out=timed_out, timeout_seconds=timeout)
    times = [wintypes.FILETIME() for _ in range(4)]
    query = ctypes.windll.kernel32.GetProcessTimes
    query.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    query.restype = wintypes.BOOL
    if query(int(process._handle), *(ctypes.byref(t) for t in times)):
        receipt["process_created"] = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    else:
        receipt["identity_observation_error"] = ctypes.GetLastError()
    RECEIPTS.append(receipt)
    # Persist before any exit, parse or semantic assertion, including timeouts.
    OUTPUT.with_name(OUTPUT.stem + "-raw-receipts.json").write_text(
        json.dumps(RECEIPTS, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert not timed_out, receipt
    assert process.returncode == 0 and not stderr, (receipt, stderr[:3000])
    return process, stdout


def run_file(rows, fault=False, env=None):
    process, raw = invoke(FAULT if fault else PROBE, held.canonical(rows), 100, env)
    values = json.loads(raw)
    assert len(values) == len(rows)
    times = [wintypes.FILETIME() for _ in range(4)]
    query = ctypes.windll.kernel32.GetProcessTimes
    query.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    query.restype = wintypes.BOOL
    assert query(int(process._handle), *(ctypes.byref(t) for t in times))
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    RECEIPTS[-1].update(process_id=process.pid, process_created=created, rows=len(rows))
    for value in values:
        assert value["fault_controls_available"] == fault
        if "result" in value:
            assert value["result"]["capture"]["process_id"] == str(process.pid)
            assert value["result"]["capture"]["process_created"] == str(created)
    return values


def run_worker(row, fault=False):
    _, raw = invoke(FAULT if fault else PROBE, held.canonical(row) + b"\n", 35)
    lines = raw.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def source_receipt(path, before, inputs, outputs):
    after = held.file_digest(path), path.stat().st_size
    SOURCE_RECEIPTS.append(dict(before_sha256=before[0], after_sha256=after[0], before_bytes=before[1], after_bytes=after[1],
                                inputs=[sha(held.canonical(v)) for v in inputs],
                                outputs=[sha(held.canonical(v)) for v in outputs]))
    OUTPUT.with_name(OUTPUT.stem + "-source-receipts.json").write_text(
        json.dumps(SOURCE_RECEIPTS, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert before == after


def row(volume, path, **extra):
    value = dict(path=str(path), offset=volume.input["offset"], length=volume.input["length"],
                 directory=copy.deepcopy(volume.input["directory"]), name_order=True,
                 limits=copy.deepcopy(volume.input["limits"]))
    value.update(extra)
    return value


def oracle(volume, capture, minor, controls=None):
    request = copy.deepcopy(volume.input)
    request.update(source_id=capture["source_identity_digest"], epoch=capture["sequence"],
                   source_bytes=capture["source_before"]["bytes"], minor=str(minor))
    request.update(controls or {})
    _, raw = invoke(PURE, held.canonical([request]), 90)
    value = json.loads(raw)[0]
    assert value["source_unchanged"] and value["refusal"] == ""
    return value["report"]


def complete(test, volume, request, result, regions):
    capture, observation = result["capture"], result["observation"]
    expected = volume.expected()
    diagnostic = "" if expected["mapped_nondecreasing"] else "ntfs_name_order_mapped_descent"
    test.assertEqual(result["schema"], "org.disked.ntfs-name-order-file-capture/1")
    test.assertFalse(result["authorizes_effects"] or result["product_dispatch_admitted"])
    test.assertEqual(observation["schema"], "org.disked.ntfs-name-order-observation-prototype/1")
    test.assertTrue(observation["complete"] and observation["reread_equal"])
    test.assertEqual(observation["diagnostic"], diagnostic)
    test.assertEqual(observation["applicable"], not diagnostic)
    test.assertEqual(capture["observed_stable"], not diagnostic)
    for key in ("profile_selection_equal", "replay_equal", "metadata_complete", "metadata_equal", "binding_checks_ok"):
        test.assertTrue(capture[key], key)
    test.assertEqual(capture["source_before"], capture["source_after"])
    test.assertEqual(capture["source_before"], capture["source_final"])
    test.assertEqual(capture["source_identity_digest"], sha(held.canonical(capture["source_before"])))
    test.assertEqual(capture["selected_profile"], "3." + volume.input["minor"])
    test.assertEqual(capture["domain"]["provider"], "ntfs-name-order-file-prototype")
    test.assertEqual(capture["capture_domain"], sha(held.canonical(capture["domain"])))
    test.assertEqual(capture["domain"]["directory_reference"], request["directory"].get("reference", "0"))
    wanted_limits = dict(entries="4096", blocks="64", bitmap_bytes="65536")
    wanted_limits.update(request["directory"].get("limits", {}))
    test.assertEqual(capture["domain"]["directory_limits"], wanted_limits)
    test.assertNotIn("target_limit", capture["domain"])
    audit, table = observation["name_order"], observation["upcase"]
    test.assertTrue(audit["complete"] and table["complete"])
    for key, value in expected.items():
        test.assertEqual(audit[key], value, key)
    for key in ("namespace_verified", "collation_verified", "target_membership_verified",
                "alias_resolution_admitted", "lookup_admitted"):
        test.assertFalse(audit[key])
    test.assertEqual(audit["case_policy"], "unobserved")
    test.assertEqual(audit["directory_sha256"], sha(held.canonical(observation["directory"])))
    test.assertEqual(audit["directory_reference"], str(volume.directory.reference))
    test.assertEqual(audit["table_sha256"], table["table_sha256"])
    test.assertEqual(table["table_sha256"], sha(volume.table.table))
    test.assertEqual(table["table_hex"], volume.table.table.hex())
    test.assertEqual(table["base_reference"], str(volume.table.reference))
    test.assertEqual(table["base_record_sha256"], sha(volume.table.base_raw))
    for value in (observation, audit, table):
        test.assertEqual(value["source_id"], capture["source_identity_digest"])
        test.assertEqual(value["epoch"], capture["sequence"])
        test.assertEqual(value["volume_offset"], volume.input["offset"])
        test.assertEqual(value["volume_bytes"], volume.input["length"])
    controls = dict(directory=copy.deepcopy(request["directory"]), limits=copy.deepcopy(request["limits"]))
    test.assertEqual(observation, oracle(volume, capture, volume.input["minor"], controls))
    wanted = volume.initial_reads * 2
    test.assertEqual([(int(v["offset"]), int(v["requested"])) for v in regions], wanted)
    from test_ntfs_capture import bytes_at
    for actual, (at, size) in zip(regions, wanted):
        test.assertEqual(bytes.fromhex(actual["bytes"]), bytes_at(volume.input, at, size))
        test.assertTrue(actual["seek_attempted"] and actual["read_attempted"])
        test.assertEqual((actual["error"], actual["refusal"]), ("0", ""))
    auto30 = volume.input["minor"] == "0" and request.get("profile", "auto") == "auto"
    prefix = len(volume.directory.bootstrap_reads) if auto30 else 0
    for key in ("profile_prefix_validation_attempted", "profile_prefix_validated", "profile_prefix_boundary", "profile_prefix_continued"):
        test.assertEqual(capture[key], auto30)
    test.assertEqual(capture["profile_prefix_validation_calls"], str(prefix))
    test.assertEqual(capture["profile_prefix_reused"], str(prefix))
    test.assertEqual(capture["profile_probe_response_count"], str(prefix if auto30 else len(wanted)))
    test.assertEqual(capture["replay_calls"], str(len(wanted) + 2 * prefix))
    test.assertEqual(capture["retained_replays"], "2" if auto30 else "1")


def layouts():
    from test_ntfs_name_order import cases
    # Use every independent geometry/tree/table/name/alias layout before fault
    # enumeration. Keep requests and diagnostics; native identities remain runtime facts.
    for name, volume, request, diagnostic, refusal in cases():
        if name.startswith("null-"):
            break
        assert not refusal
        yield name, volume, request, diagnostic


def layout_manifest():
    return [dict(case=name, source_sha256=sha(held.canonical(volume.input)),
                 expected=volume.expected(), diagnostic=diagnostic,
                 initial_reads=[dict(offset=str(at), bytes=str(n)) for at, n in volume.initial_reads],
                 regions=volume.regions(), table_sha256=sha(volume.table.table))
            for name, volume, request, diagnostic in layouts()]
