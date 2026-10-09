"""Offline static registry/identity generation. No fetched code or runtime plugins."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def parameter_schema_closure(all_schemas, schema_ids, inputs, root):
    """Bind offline references, including local JSON pointers, to exact inputs.

    The native registry indexes references by identity. Qualify local pointers
    with their owning schema ID; never fetch or merge a competing schema owner.
    """
    pending = list(sorted(schema_ids)); schemas = {}

    def qualify(node, owner):
        if isinstance(node, dict):
            result = {}
            for key, value in node.items():
                if key == '$ref':
                    if not isinstance(value, str):
                        raise ValueError('Invalid parameter schema reference')
                    value = owner + value if value.startswith('#') else value
                    pending.append(value)
                else:
                    value = qualify(value, owner)
                result[key] = value
            return result
        if isinstance(node, list):
            return [qualify(value, owner) for value in node]
        return node

    while pending:
        name = pending.pop()
        if name in schemas:
            continue
        owner, separator, fragment = name.partition('#')
        if owner not in all_schemas:
            raise ValueError('Unbound parameter schema reference: ' + name)
        value, path = all_schemas[owner]
        if path.relative_to(root).as_posix() not in inputs:
            raise ValueError('Parameter schema missing from build input closure: ' + str(path))
        if separator and fragment:
            if not fragment.startswith('/'):
                raise ValueError('Unsupported parameter schema fragment: ' + name)
            for token in fragment[1:].split('/'):
                if re.search(r'~(?![01])', token):
                    raise ValueError('Invalid parameter schema pointer: ' + name)
                token = token.replace('~1', '/').replace('~0', '~')
                if not isinstance(value, dict) or token not in value:
                    raise ValueError('Unbound parameter schema pointer: ' + name)
                value = value[token]
        schemas[name] = qualify(value, owner)
    return schemas


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def cpp(value, wide=False):
    # All generated presentation strings must be static printable ASCII.
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("Non-ASCII/control data in static bootstrap registry")
    return ("L" if wide else "") + json.dumps(value)


def write_changed(path, content):
    data = content.encode("utf-8")
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def generate(args):
    root = args.root.resolve()
    profile = read(root / "spec/catalog/native-bootstrap.json")
    commands = read(root / "spec/catalog/commands.json")["commands"]
    syntax = read(root / "spec/catalog/cli-syntax.json")
    implemented = set(profile["implemented_commands"])
    if profile["fake_provider_id"] != "provider.fake.bootstrap/1":
        raise ValueError("Private fake graph profile requires an explicit provider identity change")
    if implemented != {"build.inspect", "command.list", "protocol.serve", "mode.explain", "target.list", "target.inspect", "topology.show", "capability.explain",
                       "plan.simulate", "operation.inspect", "operation.cancel.request", "operation.watch", "shell.open", "shell.close", "image.inspect", "table.verify", "image.acquire", "health.assess", "evidence.export", "image.verify"}:
        raise ValueError("Bootstrap handlers require an explicit contract/code change")
    if args.compiler_version != profile["compiler_version"] or args.sdk != profile["sdk"] or args.configuration != "Release":
        raise ValueError("Actual build configuration differs from bootstrap profile")
    composition = next(c for c in read(root / "spec/catalog/compositions.json")["compositions"] if c["id"] == profile["composition_id"])
    if profile.get("image_provider_id") != "provider.image.raw.prototype/1":
        raise ValueError("Image profile requires an explicit provider identity change")
    if profile.get("acquisition_provider_id") != "provider.image.acquire.raw.prototype/1":
        raise ValueError("Acquisition profile requires an explicit provider identity change")
    if profile.get("report_provider_id") != "provider.report.acquisition-case.prototype/1":
        raise ValueError("Report profile requires an explicit provider identity change")
    if profile.get("verification_provider_id") != "provider.image.verify.recorded.prototype/1":
        raise ValueError("Verification profile requires an explicit provider identity change")
    if composition["scope"] != "image-only" or composition["target_id"] != profile["target_id"]:
        raise ValueError("Wrong bootstrap composition")
    components = {c["id"]: c for c in read(root / "spec/catalog/components.json")["components"]}
    selected = set(composition["components"])
    if selected != {"entry.disked.image.prototype", "provider.fake.bootstrap", "provider.image.raw.prototype", "provider.image.acquire.raw.prototype", "provider.report.acquisition-case.prototype", "provider.image.verify.recorded.prototype"}:
        raise ValueError("Image prototype closure is explicitly limited to entry, fake, raw-file observations/acquisition and recorded case report export/verification")
    for name in selected:
        if components[name]["storage_authority"] not in ("none", "fake", "image") or not set(components[name]["depends_on"]) <= selected:
            raise ValueError("Invalid bootstrap component authority/dependency")
    inputs = {}
    names = read(root / "tools/build-inputs.json")["files"]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate build input")
    for name in sorted(names):
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Build input outside source root")
        inputs[name] = sha(path.read_bytes())
    closure_digest = sha(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode())
    def git(*words):
        return subprocess.check_output([args.git, "-C", str(root), *words], encoding="utf-8").strip()
    revision = git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected an exact Git SHA-1 revision")
    compiler_hash = sha(Path(args.compiler).read_bytes())
    settings = dict(compiler_sha256=compiler_hash, compile_flags=args.compile_flags,
        link_flags=args.link_flags, cmake_version=args.cmake_version, generator=args.generator,
        configuration=args.configuration, sdk=args.sdk, toolset=profile['toolset'],
        target_options_source=inputs['CMakeLists.txt'])
    identity = dict(product=profile["product"], version=profile["version"], source_revision=revision,
        source_state="dirty" if git("status", "--porcelain", "--untracked-files=normal") else "clean",
        input_digest=closure_digest, target=profile["target_id"], composition=profile["composition_id"],
        compiler="MSVC " + args.compiler_version, sdk=args.sdk, configuration=args.configuration,
        language=profile["language"], crt=profile["crt"],
        configuration_digest=sha(json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()))
    header = ["// Generated from canonical catalogs; do not edit.", "#pragma once", "namespace bootstrap {",
        "struct Command { const char* id; const char* form; const char* summary; bool implemented; };",
        "struct Form { const wchar_t* text; unsigned command; unsigned words; };", "static const Command commands[] = {"]
    forms = []
    seen = set()
    for index, command in enumerate(commands):
        if command["availability"] != "planned":
            raise ValueError("Public contract admission needs a bootstrap projection review")
        canonical = " ".join(command["words"])
        header.append("{" + ",".join([cpp(command["id"]), cpp(canonical), cpp(command["summary"]), "true" if command["id"] in implemented else "false"]) + "},")
        for form in [canonical, *command["aliases"]]:
            if form in seen:
                raise ValueError("Duplicate command form")
            seen.add(form)
            forms.append("{" + cpp(form, True) + "," + str(index) + "," + str(len(form.split())) + "},")
    header += ["};", "static const Form forms[] = {", *forms, "};", "static const wchar_t* const unavailable_options[] = {"]
    for option in syntax["global_options"]:
        if option["id"] != "help":
            header.extend(cpp(s, True) + "," for s in option["spellings"])
    header += ["};", "static const char* const fake_provider_id = " + cpp(profile["fake_provider_id"]) + ";"]
    header += ["static const char* const image_provider_id = " + cpp(profile["image_provider_id"]) + ";"]
    header += ["static const char* const acquisition_provider_id = " + cpp(profile["acquisition_provider_id"]) + ";"]
    header += ["static const char* const report_provider_id = " + cpp(profile["report_provider_id"]) + ";"]
    header += ["static const char* const verification_provider_id = " + cpp(profile["verification_provider_id"]) + ";"]
    for key, value in identity.items():
        header.append("static const char* const " + key + " = " + cpp(value) + ";")
    schema_ids = {c['parameter_schema'] for c in commands if c['parameter_schema']}
    all_schemas = {s['$id']: (s, p) for p in sorted((root/'spec/schemas').glob('*.json'))
                   for s in [read(p)] if '$id' in s}
    if not schema_ids <= all_schemas.keys():
        raise ValueError("Missing parameter schema")
    schemas = parameter_schema_closure(all_schemas, schema_ids, inputs, root)
    for name, value in [('command_catalog_json', commands), ('syntax_json', syntax), ('parameter_schemas_json', schemas)]:
        text = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
        header.append('static const char* const '+name+' =')
        header.extend(cpp(text[i:i+1024]) for i in range(0, len(text), 1024))
        header.append(';')
    header += ["}", ""]
    args.output.mkdir(parents=True, exist_ok=True)
    write_changed(args.output / "bootstrap_registry.h", "\n".join(header))
    write_changed(args.output / "build-identity.json", json.dumps(dict(identity=identity, inputs=inputs,
        compiler_path=str(Path(args.compiler).resolve()), compiler_sha256=compiler_hash,
        build_settings=settings), indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("git", "compiler", "compiler-version", "sdk", "configuration", "compile-flags", "link-flags", "cmake-version", "generator"):
        parser.add_argument("--" + name, required=True)
    generate(parser.parse_args())
