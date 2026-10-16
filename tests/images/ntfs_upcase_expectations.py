"""Independent source/layout/table assertions shared by actual native consumers."""
import copy
from test_ntfs_capture import bytes_at
import test_ntfs_file as held
import test_ntfs_directory_file as directory_file


def foundation(observation):
    value = directory_file.foundation(observation)
    for key in ("upcase_record", "upcase"):
        if key in observation:
            value[key] = copy.deepcopy(observation[key])
    return value


def complete(test, volume, row, result, regions):
    capture, observation = result["capture"], result["observation"]
    test.assertEqual(result["schema"], "org.disked.ntfs-upcase-file-capture/1")
    test.assertEqual(observation["schema"], "org.disked.ntfs-upcase-observation-prototype/1")
    test.assertTrue(observation["complete"] and observation["applicable"] and observation["reread_equal"])
    test.assertEqual(observation["diagnostic"], "")
    test.assertNotIn("binding_diagnostic", observation)
    for key in ("observed_stable", "profile_selection_equal", "replay_equal", "metadata_complete",
                "metadata_equal", "binding_checks_ok"):
        test.assertTrue(capture[key], key)
    test.assertEqual(capture["source_before"], capture["source_after"])
    test.assertEqual(capture["source_before"], capture["source_final"])
    test.assertEqual(capture["source_identity_digest"], held.digest(held.canonical(capture["source_before"])))
    test.assertEqual(observation["source_id"], capture["source_identity_digest"])
    test.assertEqual(observation["epoch"], capture["sequence"])
    test.assertEqual(capture["selected_profile"], "3." + volume.input["minor"])
    test.assertEqual(capture["domain"]["provider"], "ntfs-upcase-file-prototype")
    test.assertNotIn("directory_reference", capture["domain"])
    test.assertNotIn("directory_limits", capture["domain"])
    test.assertNotIn("target_limit", capture["domain"])
    test.assertEqual(capture["capture_domain"], held.digest(held.canonical(capture["domain"])))
    table = observation["upcase"]
    test.assertEqual(table["schema"], "org.disked.ntfs-upcase-table-observation/1")
    test.assertTrue(table["complete"])
    test.assertEqual(table["table_hex"], volume.table.hex())
    test.assertEqual(table["table_sha256"], held.digest(volume.table))
    test.assertEqual(table["base_reference"], str(volume.reference))
    test.assertEqual(table["base_record_sha256"], held.digest(volume.base_raw))
    test.assertEqual(table["table_bytes"], "131072")
    test.assertEqual(table["source_id"], observation["source_id"])
    test.assertEqual(table["epoch"], observation["epoch"])
    test.assertEqual(table["volume_offset"], volume.input["offset"])
    test.assertEqual(table["volume_bytes"], volume.input["length"])
    test.assertEqual(table["volume_serial"], str(int.from_bytes(bytes_at(volume.input, volume.offset + 72, 8), "little")))
    wanted = volume.initial_reads * 2
    test.assertEqual([(int(r["offset"]), int(r["requested"])) for r in regions], wanted)
    for region, (at, size) in zip(regions, wanted):
        test.assertEqual(bytes.fromhex(region["bytes"]), bytes_at(volume.input, at, size))
        test.assertTrue(region["seek_attempted"] and region["read_attempted"])
        test.assertEqual((region["error"], region["refusal"]), ("0", ""))
    automatic30 = volume.input["minor"] == "0" and row.get("profile", "auto") == "auto"
    prefix = len(volume.bootstrap_reads) if automatic30 else 0
    for key in ("profile_prefix_validation_attempted", "profile_prefix_validated",
                "profile_prefix_boundary", "profile_prefix_continued"):
        test.assertEqual(capture[key], automatic30)
    test.assertEqual(capture["profile_probe_response_count"], str(prefix if automatic30 else len(wanted)))
    test.assertEqual(capture["profile_prefix_validation_calls"], str(prefix))
    test.assertEqual(capture["profile_prefix_reused"], str(prefix))
    test.assertEqual(capture["replay_calls"], str(len(wanted) + 2 * prefix))
    test.assertEqual(capture["retained_replays"], "2" if automatic30 else "1")
    if automatic30:
        test.assertEqual(capture["profile_probe_foundation_sha256"], capture["profile_selected_foundation_sha256"])
    test.assertFalse(result["authorizes_effects"] or result["product_dispatch_admitted"] or capture["atomic_snapshot"])
    test.assertFalse(any(observation[k] for k in ("atomic_snapshot", "current_source_authority", "effects_authorized")))


def prefix_reports(test, volume, row, value):
    capture = value["result"]["capture"]
    automatic30 = volume.input["minor"] == "0" and row.get("profile", "auto") == "auto"
    if not automatic30:
        return
    probe = directory_file.pure_report(volume, value, 1)
    boundary = directory_file.pure_report(volume, value, 0,
        {"fault": dict(mode="throw", call=str(len(volume.bootstrap_reads) + 1))})
    selected = directory_file.pure_report(volume, value, 0)
    test.assertEqual(capture["profile_probe_sha256"], held.digest(held.canonical(probe)))
    test.assertEqual(capture["profile_prefix_validation_sha256"], held.digest(held.canonical(boundary)))
    test.assertEqual(capture["profile_probe_foundation_sha256"], held.digest(held.canonical(foundation(probe))))
    test.assertEqual(capture["profile_selected_foundation_sha256"], held.digest(held.canonical(foundation(boundary))))
    test.assertEqual(value["result"]["observation"], selected)
