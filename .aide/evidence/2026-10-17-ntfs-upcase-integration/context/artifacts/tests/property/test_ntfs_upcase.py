"""Independent supplied-table words and unsigned UTF16 sequence order recipes."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def encoded(units):
    return struct.pack("<" + "H" * len(units), *units)


def order(left, right):
    # Python's list order is an independent unsigned-integer lexicographic oracle.
    return (left > right) - (left < right)


def tables():
    identity = list(range(65536))
    ascii_map = identity.copy()
    for unit in range(ord("a"), ord("z") + 1):
        ascii_map[unit] = unit - 32
    ascii_map[0x00E4] = 0x00C4
    ascii_map[0x03C3] = ascii_map[0x03C2] = 0x03A3
    ascii_map[0x0131] = 0x0049
    return {
        "identity": identity,
        "selected-case-pairs": ascii_map,
        "permuted-words": [(n * 40503 + 257) % 65536 for n in identity],
        "zero-words": [0] * 65536,
        "maximum-words": [65535] * 65536,
    }


def queries():
    pairs = [([], []), ([], [0]), ([0], []), ([0], [0, 0]),
             ([97], [65]), ([65], [97]), ([0xE4], [0xC4]),
             ([0x03C2], [0x03C3]), ([0x0131], [73]), ([0xDF], [83, 83]),
             ([0xD800], [0xD801]), ([0xDC00], [0xD800]),
             ([0xD800, 0xDC00], [0xE000]), ([0, 97], [0, 65]),
             ([65535], [65534]), ([0xFEFF], [0xFFFF]),
             ([1] * 254 + [2], [1] * 254 + [3]),
             ([1] * 255, [1] * 254), ([97, 66], [65, 65]),
             ([0], [65535]), ([255], [256]), ([511], [512]),
             ([65279], [65280]), ([65534], [65535])]
    rng = random.Random(0xD15CED099)
    for _ in range(120):
        size = rng.choice([0, 1, 2, 3, 31, 254, 255])
        left = [rng.randrange(65536) for _ in range(size)]
        right = left.copy()
        if right:
            right[rng.randrange(size)] = rng.randrange(65536)
        pairs.extend([(left, right), (right, left), (left, left)])
    # Explicit triples exercise transitivity independently of the pair oracle.
    triples = []
    for _ in range(40):
        triple = [[rng.randrange(65536) for _ in range(rng.randrange(8))] for _ in range(3)]
        triples.append(triple)
        pairs.extend([(triple[0], triple[1]), (triple[1], triple[2]), (triple[0], triple[2])])
    return pairs, triples


def expected_facts():
    pairs, triples = queries()
    facts = []
    for name, table in tables().items():
        expected = [{"raw_order": order(a, b),
                     "upcase_order": order([table[n] for n in a], [table[n] for n in b])}
                    for a, b in pairs]
        facts.append({"table": name, "table_sha256": sha(encoded(table)),
                      "mapping_units": 65536, "comparison_cases": len(pairs),
                      "expected_comparisons_sha256": sha(json.dumps(expected, sort_keys=True,
                                                                     separators=(",", ":")).encode()),
                      "transitivity_triples": len(triples)})
    return facts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pairs, triples = queries()
    facts = expected_facts()
    result = {"schema": "org.disked.ntfs-upcase-test-results/1", "status": "expected-only",
              "recipe_sha256": sha(Path(__file__).read_bytes()), "tables": facts,
              "mapping_units": len(facts) * 65536,
              "comparison_cases": len(facts) * len(pairs), "native_probe_run": False}

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    if args.probe is None:
        return
    result["native_probe_run"] = True
    result["native_probe_sha256"] = sha(args.probe.read_bytes())
    result["observations"] = []
    try:
        for name, table in tables().items():
            row = {"table_hex": encoded(table).hex(),
                   "queries": [{"left_hex": encoded(a).hex(), "right_hex": encoded(b).hex()}
                               for a, b in pairs]}
            completed = subprocess.run([str(args.probe)], input=json.dumps([row]).encode(),
                                       capture_output=True, timeout=30)
            observation = {"table": name, "exit_code": completed.returncode,
                           "stderr": completed.stderr.decode("utf-8", errors="replace"),
                           "stdout_sha256": sha(completed.stdout)}
            result["observations"].append(observation)
            # Retain actual bytes before checking an expected result.
            args.output.with_name(args.output.stem + "-" + name + ".response.json").write_bytes(completed.stdout)
            save()
            assert completed.returncode == 0 and not completed.stderr, observation
            rows = json.loads(completed.stdout)
            assert len(rows) == 1
            actual = rows[0]
            assert actual["mapped_hex"] == encoded(table).hex(), name
            expected = [{"raw_order": order(a, b),
                         "upcase_order": order([table[n] for n in a], [table[n] for n in b])}
                        for a, b in pairs]
            assert actual["orders"] == expected, name
            # Triples occupy the final120 cases. Check the algebraic claim too.
            for index in range(len(pairs) - len(triples) * 3, len(pairs), 3):
                for key in ("raw_order", "upcase_order"):
                    ab, bc, ac = [actual["orders"][j][key] for j in range(index, index + 3)]
                    assert not (ab <= 0 and bc <= 0) or ac <= 0
                    assert not (ab >= 0 and bc >= 0) or ac >= 0
            observation["passed"] = True
        result["status"] = "pass"
    except BaseException as error:
        result.update(status="fail", error=repr(error))
        save()
        raise
    save()
    print(json.dumps({"status": result["status"], "mapping_units": result["mapping_units"],
                      "comparison_cases": result["comparison_cases"]}))


if __name__ == "__main__":
    main()
