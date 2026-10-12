"""Check private native boundaries using CMake's generated codemodel and headers.

This is a lexical quoted-include and generated build-closure check, not a C++
preprocessor, public ABI qualification, or a direct-link dependency audit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def load_codemodel(root, build, configuration):
    reply = build / ".cmake/api/v1/reply"
    indexes = sorted(reply.glob("index-*.json"))
    if not indexes:
        raise ValueError("No CMake file-api reply; configure the current checkout first")
    index = json.loads(indexes[-1].read_bytes())
    refs = [v for v in index["objects"] if v["kind"] == "codemodel" and v["version"]["major"] == 2]
    if len(refs) != 1:
        raise ValueError("Expected one codemodel v2 reply")
    model = json.loads((reply / refs[0]["jsonFile"]).read_bytes())
    if Path(model["paths"]["source"]).resolve() != root or Path(model["paths"]["build"]).resolve() != build:
        raise ValueError("CMake reply belongs to a different source or build directory")
    configs = [v for v in model["configurations"] if v["name"] == configuration]
    if len(configs) != 1:
        raise ValueError("Requested build configuration is absent or ambiguous")
    targets = [json.loads((reply / v["jsonFile"]).read_bytes()) for v in configs[0]["targets"]]
    return targets, {
        "cmake_version": index["cmake"]["version"]["string"],
        "configuration": configuration,
        "index_sha256": hashlib.sha256(indexes[-1].read_bytes()).hexdigest(),
    }


def owner(path):
    parts = Path(path).parts
    if len(parts) > 2 and parts[0] == "source":
        if parts[1] == "apps" and len(parts) > 4 and parts[3] in {"gui", "tui", "shell"}:
            return "frontend-model"
        return parts[1]
    return None


def forbidden(origin, destination):
    return (
        origin == "portable" and destination not in {None, "portable"}
        or origin == "runtime" and destination not in {None, "portable", "runtime"}
        or origin == "providers" and destination in {"apps", "frontend-model"}
        or origin == "frontend-model" and destination not in {None, "portable", "runtime", "frontend-model"}
    )


def quoted_includes(text, defines, configured_guards):
    """Track explicitly declared compile-only guards; unknowns stay possible.

    This is not preprocessing. Compiler/platform macros, expressions and elif
    remain conservative; only configured ifdef/ifndef branches are known.
    """
    active, stack = True, []
    symbols = set(defines)
    for line in text.splitlines():
        directive = re.match(r'^\s*#\s*(\w+)(.*)$', line)
        if not directive:
            continue
        kind, body = directive.groups()
        body = body.strip()
        if kind in {"ifdef", "ifndef", "if"}:
            symbol = body.split()[0] if body else ""
            choice = (symbol in symbols) if kind in {"ifdef", "ifndef"} and symbol in configured_guards else None
            if kind == "ifndef" and choice is not None:
                choice = not choice
            stack.append((active, choice))
            active = active and choice is not False
        elif kind in {"else", "elif"} and stack:
            parent, choice = stack[-1]
            if kind == "elif":
                choice = None
                stack[-1] = (parent, choice)
            active = parent and (choice is not True if choice is not None else True)
        elif kind == "endif" and stack:
            active, _ = stack.pop()
        elif kind == "define" and active and body:
            if body.split()[0] in configured_guards:
                raise ValueError("Compile-only include guard redefined in source: " + body.split()[0])
            symbols.add(body.split()[0])
        elif kind == "undef" and active:
            if body in configured_guards:
                raise ValueError("Compile-only include guard undefined in source: " + body)
            symbols.discard(body)
        elif kind == "include":
            value = re.match(r'^"([^"\r\n]+)"', body)
            if value:
                yield value.group(1), active


def inspect(root, build, targets, contract, usage=None):
    violations = []
    by_id = {v["id"]: v for v in targets}
    by_name = {v["name"]: v for v in targets}
    resolved = set()
    text_cache = {}
    strict = contract.get("qualified_includes", False)
    header_usage = usage.get("targets", {}) if usage else {}
    if strict and (not usage or usage.get("schema") != "org.disked.private-header-usage/1"):
        violations.append("Missing current CMake private header-usage projection")
    inventory = {p.relative_to(root).as_posix().lower(): p.relative_to(root).as_posix()
                 for folder in (root / "source", root / "tests") for p in folder.rglob("*") if p.is_file()}

    def relative(path):
        path = path.resolve()
        if path.is_relative_to(root):
            return path.relative_to(root).as_posix()
        if path.is_relative_to(build):
            return "<build>/" + path.relative_to(build).as_posix()
        return str(path)

    def closure(target):
        seen = set()
        pending = [v["id"] for v in target.get("dependencies", [])]
        while pending:
            name = pending.pop()
            if name not in by_id:
                violations.append(f"{target['name']}: missing dependency {name}")
            elif name not in seen:
                seen.add(name)
                pending.extend(v["id"] for v in by_id[name].get("dependencies", []))
        return seen

    def compiled(target):
        return [v for v in target.get("sources", []) if "compileGroupIndex" in v]

    def visible_headers(name):
        if name not in header_usage:
            if strict and by_name[name].get("type") != "UTILITY":
                violations.append(f"{name}: missing header-usage target")
            return set()
        node = header_usage[name]
        visible = set(node["headers"])
        seen = set()
        pending = list(node["direct"])
        while pending:
            dependency = pending.pop()
            if dependency in seen:
                continue
            seen.add(dependency)
            if dependency not in header_usage:
                violations.append(f"{name}: unknown compile-usage dependency {dependency}")
                continue
            dependency_node = header_usage[dependency]
            visible.update(dependency_node["interface_headers"])
            pending.extend(dependency_node["interface"])
        return visible

    visibility = {v["name"]: visible_headers(v["name"]) for v in targets}
    if strict:
        for target in targets:
            node = header_usage.get(target["name"])
            if node:
                actual_headers = {v["path"] for v in target.get("sources", []) if v["path"].endswith(".h")}
                if not set(node["headers"]) <= actual_headers:
                    violations.append(f"{target['name']}: header ownership absent from codemodel sources")
                if not set(node["interface_headers"]) <= set(node["headers"]):
                    violations.append(f"{target['name']}: exported header has no owning source")

    def target_owners(target):
        return {owner(v["path"]) for v in compiled(target)} - {None}

    def visit(target, path, includes, seen, defines):
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        if not path.is_file():
            violations.append(f"{target['name']}: missing source/header {relative(path)}")
            return
        if key not in text_cache:
            text_cache[key] = path.read_text(encoding="utf-8")
        for name, active in quoted_includes(text_cache[key], defines, set(contract.get("compile_only_include_guards", []))):
            candidates = set()
            for base in [path.parent, *includes]:
                supplied = Path(os.path.abspath(base / name))
                if supplied.is_file():
                    # Windows resolve() canonicalizes the spelling. Inspect the
                    # lexical candidate before losing a wrong-case include.
                    if supplied.is_relative_to(root):
                        spelling = supplied.relative_to(root).as_posix()
                        actual = inventory.get(spelling.lower())
                        if actual is not None and actual != spelling:
                            violations.append(f"{target['name']}: include case {spelling}; actual {actual}")
                    candidates.add(supplied.resolve())
            if len(candidates) != 1:
                violations.append(f"{target['name']}: {relative(path)} include {name}: "
                                  + ("unresolved" if not candidates else "ambiguous " + str(sorted(map(relative, candidates)))))
                continue
            included = candidates.pop()
            source_name, header_name = relative(path), relative(included)
            actual = inventory.get(header_name.lower())
            if actual is not None and actual != header_name:
                violations.append(f"{target['name']}: include case {header_name}; actual {actual}")
            if forbidden(owner(source_name), owner(header_name)):
                violations.append(f"{target['name']}: forbidden include {source_name} -> {header_name}")
            if strict and header_name.startswith("source/"):
                if active and header_name not in visibility[target["name"]]:
                    violations.append(f"{target['name']}: undeclared header dependency {source_name} -> {header_name}")
                if path.parent != included.parent and name != header_name[len("source/"):]:
                    violations.append(f"{target['name']}: unqualified cross-module include {source_name}: {name}")
            resolved.add((target["name"], source_name, name, header_name))
            # Generated project headers are inspected too; SDK/system headers
            # use angle brackets and are qualified by compiler/import evidence.
            if active and (included.is_relative_to(root) or included.is_relative_to(build)):
                visit(target, included, includes, seen, defines)

    for target in targets:
        origins = target_owners(target)
        dependencies = closure(target)
        # Executable compositions intentionally compile product wiring and
        # concrete host/provider adapters together. Enforce each source's
        # include boundary, but do not misclassify that wiring as a provider.
        if target.get("type") in {"STATIC_LIBRARY", "OBJECT_LIBRARY"}:
            for origin in origins:
                if any(forbidden(origin, other) for other in origins):
                    violations.append(f"{target['name']}: mixed ownership across forbidden layers")
        dependency_origins = origins if len(origins) == 1 else set()
        for dependency in dependencies:
            for origin in dependency_origins:
                for destination in target_owners(by_id[dependency]):
                    if forbidden(origin, destination):
                        violations.append(f"{target['name']}: forbidden build dependency {by_id[dependency]['name']}")
        for source in compiled(target):
            group = target["compileGroups"][source["compileGroupIndex"]]
            path = Path(source["path"])
            if not path.is_absolute():
                path = root / path
            if path.suffix.lower() not in {".c", ".cpp", ".cc", ".cxx"}:
                continue
            includes = [Path(v["path"]) for v in group.get("includes", [])]
            defines = {v["define"].split("=", 1)[0] for v in group.get("defines", [])}
            for fragment in group.get("compileCommandFragments", []):
                defines.update(re.findall(r'(?:^|\s)[/-]D(DISKED_[A-Za-z0-9_]+)', fragment["fragment"]))
            visit(target, path.resolve(), includes, set(), defines)

    for name, expected in contract["core_targets"].items():
        target = by_name.get(name)
        if target is None:
            violations.append(f"Missing core target {name}")
            continue
        actual = sorted(v["path"] for v in compiled(target))
        if actual != sorted(expected["sources"]):
            violations.append(f"{name}: unexpected compiled sources {actual}")
        dependencies = {by_id[v]["name"] for v in closure(target) if compiled(by_id[v])}
        if dependencies != set(expected["build_closure"]):
            violations.append(f"{name}: unexpected build closure {sorted(dependencies)}")
        for group in target.get("compileGroups", []):
            flags = " ".join(v["fragment"] for v in group.get("compileCommandFragments", []))
            # MSVC accepts '/' and '-' option prefixes; CMake's codemodel uses
            # -MT for the runtime property although the project records /MT.
            options = {v[1:] for v in flags.split() if v.startswith(("/", "-"))}
            for flag in contract["required_compile_flags"]:
                if flag[1:] not in options:
                    violations.append(f"{name}: missing compile option {flag}")
            if group.get("languageStandard", {}).get("standard") != "14":
                violations.append(f"{name}: C++14 not recorded")

    for name, excluded in contract["isolated_consumers"].items():
        target = by_name.get(name)
        if target is None:
            violations.append(f"Missing isolation consumer {name}")
        else:
            dependencies = {by_id[v]["name"] for v in closure(target)}
            for other in excluded:
                if other in dependencies:
                    violations.append(f"{name}: unwanted build dependency {other}")

    return {
        "status": "FAIL" if violations else "PASS",
        "target_count": len(targets),
        "compiled_source_entries": sum(len(compiled(v)) for v in targets),
        "quoted_include_edges": len(resolved),
        "violations": sorted(set(violations)),
        "targets": {v["name"]: {"sources": [s["path"] for s in compiled(v)],
                                  "build_closure": sorted(by_id[d]["name"] for d in closure(v))} for v in targets},
        "resolved_includes": [dict(zip(("target", "including_file", "include", "resolved_file"), v)) for v in sorted(resolved)],
        "visible_headers": {name: sorted(values) for name, values in visibility.items()},
        "limits": ["Lexical quoted includes, including conditional branches; not preprocessing.",
                   "Generated build closure includes transitive/order dependencies; not direct links.",
                   "Five core headers and presentation requests.h/session.h have separate compiler self-containment checks.",
                   "No OS/SDK import, ABI, storage authority or full portability qualification."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--configuration", default="Release")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root, build = args.root.resolve(), args.build.resolve()
    targets, metadata = load_codemodel(root, build, args.configuration)
    contract = json.loads((root / "spec/catalog/source-maintenance-prototype.json").read_bytes())["build_checks"]
    projection = build / "private-header-usage.json"
    usage = json.loads(projection.read_bytes()) if projection.is_file() else None
    result = inspect(root, build, targets, contract, usage)
    result["metadata"] = metadata
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: result[k] for k in ("status", "target_count", "compiled_source_entries", "quoted_include_edges", "violations")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
