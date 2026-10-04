#!/usr/bin/env python3
"""DiskEd specification bootstrap. Does not execute DiskEd or AIDE work.

Python 3.10+ coordinator; dependencies in requirements.txt. All schema reference
resolution is offline. Reading the Markdown bundle needs no Python runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 8 * 1024 * 1024
MAX_FRONTMATTER = 64 * 1024
SCHEMA_PREFIX = 'urn:disked:schema:'
U64_MAX = 18446744073709551615
SEMANTICS = {SCHEMA_PREFIX+name+':1':name for name in ('extent','graph','handoff','plan','event')}

class SpecError(Exception):
    """An explicit validation or safety refusal."""

def digest_bytes(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def canonical(value: Any) -> bytes:
    # This is the local spec-tool representation, NOT the future signed DiskEd plan format.
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')

def load_dependencies():
    try:
        import yaml
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        raise SpecError('Missing tooling dependency. Run: python -m pip install -r spec/tools/requirements.txt') from exc
    return yaml, jsonschema, Registry, Resource

def no_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SpecError('Duplicate JSON key: ' + str(key))
        result[key] = value
    return result

def parse_json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=no_duplicate_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(SpecError('Nonfinite JSON value: '+x)))
    except (json.JSONDecodeError, RecursionError) as exc:
        raise SpecError('Invalid or excessively nested JSON: '+str(exc)) from exc

def safe_path(root: Path, relative: str, *, existing: bool = False) -> Path:
    """Refuse absolute, traversing, Windows-ambiguous and symlinked paths."""
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise SpecError('Unsafe relative path: '+repr(relative))
    raw_parts = relative.split('/')
    if any(part in ('', '.', '..') for part in raw_parts):
        raise SpecError('Noncanonical relative path: '+relative)
    reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1,10)), *(f'lpt{i}' for i in range(1,10))}
    if any(part.split('.')[0].casefold() in reserved for part in raw_parts):
        raise SpecError('Reserved Windows filename: '+relative)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(p in ('..', '.') for p in pure.parts) or ':' in relative:
        raise SpecError('Path must be non-traversing and relative: '+relative)
    if any(p.rstrip(' .') != p for p in pure.parts):
        raise SpecError('Trailing dot/space in path: '+relative)
    root = root.resolve()
    target = root.joinpath(*pure.parts)
    cur = root
    for part in pure.parts:
        cur = cur / part
        if cur.is_symlink():
            raise SpecError('Symlink is not permitted in managed path: '+str(cur))
    try:
        target.resolve().relative_to(root)
    except ValueError as exc:
        raise SpecError('Path escapes root: '+relative) from exc
    if existing and not target.is_file():
        raise SpecError('Missing regular file: '+relative)
    return target

def read_text(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SpecError('Not a regular non-symlink file: '+str(path))
    if path.stat().st_size > MAX_FILE:
        raise SpecError('File exceeds bootstrap size limit: '+str(path))
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeError as exc:
        raise SpecError('Non UTF-8 text: '+str(path)) from exc

def read_json(path: Path):
    return parse_json(read_text(path))

def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SpecError('Refusing symlink output: '+str(path))
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    tmp = path.with_name(path.name + '.tmp')
    if tmp.exists() or tmp.is_symlink():
        raise SpecError('Temporary output already exists: '+str(tmp))
    try:
        with tmp.open('x', encoding='utf-8', newline='\n') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists(): tmp.unlink()

def parse_frontmatter(text: str):
    yaml, _, _, _ = load_dependencies()
    if not text.startswith('---\n'):
        raise SpecError('Missing YAML frontmatter')
    end = text.find('\n---\n', 4)
    if end < 0 or end > MAX_FRONTMATTER:
        raise SpecError('Unterminated or oversized frontmatter')
    raw = text[4:end]
    try:
        for token in yaml.scan(raw):
            if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken)):
                raise SpecError('YAML aliases, anchors and custom tags are forbidden by the DiskEd producer profile')
        class Loader(yaml.SafeLoader):
            pass
        # Leave dates as strings; the schema validates their intended representation.
        Loader.yaml_implicit_resolvers = {
            k: [(tag, rx) for tag, rx in rules if tag != 'tag:yaml.org,2002:timestamp']
            for k, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
        }
        def mapping(loader, node, deep=False):
            result = {}
            for keynode, valnode in node.value:
                key = loader.construct_object(keynode, deep=deep)
                if not isinstance(key, str):
                    raise SpecError('Frontmatter mapping keys must be strings')
                if key in result:
                    raise SpecError('Duplicate YAML key: '+key)
                result[key] = loader.construct_object(valnode, deep=deep)
            return result
        Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        meta = yaml.load(raw, Loader=Loader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise SpecError('Invalid YAML: '+str(exc)) from exc
    if not isinstance(meta, dict):
        raise SpecError('Frontmatter must be a mapping')
    return meta, text[end+5:]

def acyclic(edges: dict[str, list[str]], label='dependency graph'):
    visited, active, chain = set(), set(), []
    def visit(node):
        if node in active:
            raise SpecError(label+' cycle: '+' -> '.join(chain+[node]))
        if node in visited: return
        if node not in edges: raise SpecError(label+' unknown node: '+node)
        active.add(node); chain.append(node)
        for dep in edges[node]: visit(dep)
        chain.pop(); active.remove(node); visited.add(node)
    for node in sorted(edges): visit(node)

def unique_ids(items, label):
    result = {}
    for item in items:
        id = item['id']
        if id in result: raise SpecError('Duplicate '+label+' ID: '+id)
        result[id] = item
    return result

def bounded_u64(value, label):
    if not isinstance(value,str) or not re.fullmatch(r'0|[1-9][0-9]{0,19}',value) or int(value)>U64_MAX:
        raise SpecError(label+' is outside the decimal u64 model')
    return int(value)

def semantic_validate(kind: str | None, value: dict):
    if kind == 'extent':
        start = bounded_u64(value['start_lba'],'start_lba')
        length = bounded_u64(value['length_lba'],'length_lba')
        if start < 0 or length <= 0 or start > U64_MAX or length > U64_MAX or start + length > U64_MAX:
            raise SpecError('Extent empty or outside bounded u64 address model')
        if (start + length) * value['logical_block_bytes'] > U64_MAX:
            raise SpecError('Extent byte conversion overflows the declared u64 byte model')
    elif kind == 'graph':
        nodes = unique_ids(value['nodes'],'graph node')
        for edge in value['edges']:
            if edge['from'] not in nodes or edge['to'] not in nodes:
                raise SpecError('Dangling graph edge')
        # Resource graphs intentionally need not be DAGs.
    elif kind == 'handoff':
        for test in value['tests']:
            if test['status']=='not_run' and (test['exit_code'] is not None or test['evidence_path'] is not None):
                raise SpecError('Unrun test cannot have an exit code or execution evidence')
            if test['status']=='pass' and (test['exit_code']!=0 or not test['evidence_path']):
                raise SpecError('Passing test needs zero exit code and actual evidence reference')
    elif kind == 'plan':
        steps = unique_ids(value['steps'],'plan step')
        acyclic({id:s['depends_on'] for id,s in steps.items()}, 'action graph')
        if value['execution_environment'] != 'fake' and value['recovery_class'] != 'read-only' and not value['recovery_reference']:
            raise SpecError('Mutation plan has no declared recovery reference')
    elif kind == 'event':
        bounded_u64(value['sequence'],'event sequence')

class GitSnapshot:
    """Read exact local Git blobs without checkout, filters, hooks or fetching."""
    def __init__(self, root, revision):
        if not re.fullmatch(r'[0-9a-f]{40}',revision):raise SpecError('Review requires an exact Git revision')
        self.prefix=['git','--no-optional-locks','--no-replace-objects','-c','core.fsmonitor=false','-C',str(root)]
        result=subprocess.run(self.prefix+['ls-tree','-r','-z','-l',revision],capture_output=True,timeout=20)
        if result.returncode:raise SpecError('Reviewed Git revision unavailable locally: '+revision)
        self.entries={};self.cache={}
        for raw in result.stdout.split(b'\0'):
            if not raw:continue
            meta,path=raw.split(b'\t',1);mode,kind,oid,size=meta.split()
            self.entries[path.decode('utf-8')]=(mode,kind,oid,int(size) if size!=b'-' else -1)

    def read_many(self, paths):
        wanted=list(dict.fromkeys(p for p in paths if p not in self.cache))
        total=0
        for path in wanted:
            if path not in self.entries:raise SpecError('Missing reviewed blob: '+path)
            mode,kind,_,size=self.entries[path]
            if mode not in (b'100644',b'100755') or kind!=b'blob' or not 0<=size<=MAX_FILE:
                raise SpecError('Invalid reviewed regular file: '+path)
            total+=size
        if total>32*MAX_FILE:raise SpecError('Reviewed input batch exceeds byte budget')
        if not wanted:return
        result=subprocess.run(self.prefix+['cat-file','--batch'],input=b'\n'.join(self.entries[p][2] for p in wanted)+b'\n',capture_output=True,timeout=30)
        if result.returncode:raise SpecError('Cannot read reviewed blobs')
        stream=io.BytesIO(result.stdout)
        for path in wanted:
            oid,kind,size=stream.readline().strip().split()
            size=int(size)
            if (oid,kind,size)!=(self.entries[path][2],b'blob',self.entries[path][3]):raise SpecError('Reviewed blob identity mismatch')
            data=stream.read(size)
            if len(data)!=size or stream.read(1)!=b'\n':raise SpecError('Incomplete reviewed blob')
            self.cache[path]=data

    def read(self,path):
        self.read_many([path]);return self.cache[path]

class Bundle:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root).resolve()
        self.meta = read_json(safe_path(self.root, 'bundle.json', existing=True))
        self.concepts = unique_ids(read_json(self.root/'catalog/concepts.json')['concepts'],'concept')
        self.work = unique_ids(read_json(self.root/'work/units.json')['units'],'work')
        self.schemas = {}
        yaml, jsonschema, Registry, Resource = load_dependencies()
        self.jsonschema = jsonschema
        resources = []
        for path in sorted((self.root/'schemas').glob('*.schema.json')):
            schema = read_json(path)
            jsonschema.Draft202012Validator.check_schema(schema)
            if schema['$id'] in self.schemas: raise SpecError('Duplicate schema ID')
            self.schemas[schema['$id']] = schema
            resources.append((schema['$id'], Resource.from_contents(schema)))
        def reject_remote(uri):
            raise SpecError('External schema retrieval forbidden: '+uri)
        self.registry = Registry(retrieve=reject_remote).with_resources(resources)

    def validate(self, schema_id, value, semantic=None):
        if schema_id not in self.schemas: raise SpecError('Unknown local schema: '+schema_id)
        validator = self.jsonschema.Draft202012Validator(self.schemas[schema_id], registry=self.registry,
                                                       format_checker=self.jsonschema.FormatChecker())
        errors = sorted(validator.iter_errors(value), key=lambda e: str(e.json_path))
        if errors: raise SpecError('; '.join(e.json_path+': '+e.message for e in errors[:8]))
        inferred=SEMANTICS.get(schema_id)
        # The optional legacy selector may confirm semantics, never disable or
        # substitute the contract belonging to this schema identity.
        if semantic is not None and semantic != (inferred or ('composition' if schema_id==SCHEMA_PREFIX+'composition:1' else None)):
            raise SpecError('Semantic selector does not match schema identity')
        semantic_validate(inferred, value)
        if schema_id == SCHEMA_PREFIX+'composition:1':
            self.validate_composition(value)
        if schema_id == SCHEMA_PREFIX+'target:1' and value['status']=='qualified':
            # Evidence references are still claims; refuse visibly unresolved profiles.
            for field in ('architecture','abi','executable_format','runtime'):
                if re.search(r'unknown|unresolved|\bselected\b|\btbd\b|\bor\b|/', value[field], re.I):
                    raise SpecError('Qualified target has unresolved '+field)

    def component_registry(self):
        components=unique_ids(read_json(self.root/'catalog/components.json')['components'],'component')
        for component in components.values():
            if component['role'] not in ('core','frontend','gui','provider','entry'):
                raise SpecError('Unknown component role: '+component['id'])
            if component['storage_authority'] not in ('none','fake','image','physical'):
                raise SpecError('Unknown component storage authority: '+component['id'])
            for spec in component['spec_ids']:
                if spec not in self.concepts:raise SpecError('Unknown component spec: '+spec)
        acyclic({id:c['depends_on'] for id,c in components.items()},'component graph')
        return components

    def validate_composition(self, value):
        components=self.component_registry()
        targets=unique_ids(read_json(self.root/'catalog/targets.json')['targets'],'target')
        if value['target_id'] not in targets:raise SpecError('Unknown composition target')
        selected=set(value['components'])
        if not selected <= components.keys():raise SpecError('Unknown composition component')
        if not set(value['optional_runtime_components']) <= selected:
            raise SpecError('Optional runtime component is not selected')
        for id in selected:
            if not set(components[id]['depends_on']) <= selected:
                raise SpecError('Missing component dependency: '+id)
        if sum(components[id]['role']=='gui' for id in selected)>1:
            raise SpecError('Composition selects multiple GUI adapters')
        if sum(components[id]['role']=='entry' for id in selected)!=1:
            raise SpecError('Composition must select exactly one entrypoint')
        permitted={'fake-only':{'none','fake'},'image-only':{'none','fake','image'},
                   'qualified-operations':{'none','fake','image','physical'}}[value['scope']]
        if any(components[id]['storage_authority'] not in permitted for id in selected):
            raise SpecError('Component authority exceeds composition scope')
        artifacts=unique_ids(value['artifacts'],'composition artifact')
        # Containment also depends on the finalized child bytes. Check the union
        # so a mixed containment/hash cycle cannot slip through separate DAGs.
        acyclic({id:list(set(a['contains']+a['hash_dependencies'])) for id,a in artifacts.items()},
                'artifact finalization graph')

    def document(self, id):
        aliases = read_json(self.root/'catalog/aliases.json')['aliases']
        seen = set()
        while id in aliases:
            if id in seen: raise SpecError('Alias cycle')
            seen.add(id); id = aliases[id]
        if id not in self.concepts: raise SpecError('Unknown concept: '+id)
        path = safe_path(self.root, self.concepts[id]['path'], existing=True)
        text = read_text(path)
        meta, body = parse_frontmatter(text)
        return path, meta, body, text

    def requirements(self):
        reqs, tests = [], []
        for id in sorted(self.concepts):
            path, meta, body, text = self.document(id)
            found=[]
            pattern=r'^### (DE-REQ-[A-Z0-9-]+)\n\n(.*?)\n\n\*\*Verification:\*\* (.*?)(?=\n\n(?:### |## )|\Z)'
            for m in re.finditer(pattern,body,re.M|re.S):
                rid, statement, verification = m.groups(); verification=verification.strip()
                tid=rid.replace('DE-REQ-','DE-TEST-',1)
                found.append(rid)
                reqs.append(dict(id=rid,spec=id,statement=statement.strip(),verification=verification,
                                 test_ids=[tid],implementation_status='evidence_owned_elsewhere'))
                tests.append(dict(id=tid,requirement_ids=[rid],method=verification,status='definition_only',evidence=[]))
            if found != meta['disked']['requirements']:
                raise SpecError('Requirement headings/frontmatter mismatch in '+str(path))
        unique_ids(reqs,'requirement'); unique_ids(tests,'test')
        return reqs,tests

    def generated_files(self):
        reqs,tests=self.requirements()
        nodes=[]
        for id in sorted(self.concepts):
            path,meta,body,text=self.document(id)
            nodes.append(dict(id=id,path=self.concepts[id]['path'],title=meta['title'],
                              summary=meta['description'],sha256=digest_bytes(path.read_bytes()),bytes=path.stat().st_size,
                              depends_on=meta['disked']['depends_on'],requirement_ids=meta['disked']['requirements']))
        out={}
        def put_json(path,obj):out[path]=json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
        put_json('generated/index.json',{'schema':'org.disked.spec-index/1','bundle_version':self.meta['version'],'concepts':nodes})
        put_json('catalog/requirements.json',{'schema':'org.disked.requirements/1','generated_from':'authored normative requirement headings','requirements':reqs})
        put_json('catalog/tests.json',{'schema':'org.disked.test-catalog/1','tests':tests})
        groups={}
        for n in nodes: groups.setdefault(str(PurePosixPath(n['path']).parent),[]).append(n)
        header='---\ntitle: DiskEd specification index\nokf_version: "0.2"\n---\n\n# DiskEd specification\n\n**Proposed baseline '+self.meta['version']+'. Owner acceptance pending. No product or hardware qualification.**\n\n'
        header+='Start with [Start here](START-HERE.md), [authority](foundation/authority.md), [roadmap](roadmap/implementation.md), and [open decisions](roadmap/decisions.md).\n\n'
        header+='## Working entrypoints\n\n```text\npython spec/tools/specctl.py check\npython -m unittest discover -s spec/tools/tests -v\npython spec/tools/specctl.py next\npython spec/tools/specctl.py context --work DE-W000 --output .aide-local/context/review --byte-budget 180000\n```\n\n'
        header+='The `specctl` utility manages this specification only. It does not execute DiskEd, apply AIDE work, elevate or access raw storage. [Work definitions](work/units.json), [source registry](references/sources.json), [command catalog](catalog/commands.json), [target catalog](catalog/targets.json), [schemas](schemas/index.md) and [tool contract](development/specctl.md) are local, reviewable files.\n\n'
        for group in sorted(groups):
            header+='## '+('Entry' if group=='.' else group.replace('-',' ').title())+'\n\n'
            for n in groups[group]:header+=f"- [{n['id']} — {n['title']}]({n['path']}): {n['summary']}\n"
            header+='\n'
        header+='## Change discipline\n\nEdit canonical concepts/registries. Run `index` to refresh generated views, then `check`, tests and `manifest`. Existing integrity manifests become stale after legitimate edits. Checks do not approve content or prove runtime safety.\n'
        out['index.md']=header
        for group,ns in groups.items():
            if group=='.':continue
            t='# '+group.replace('-',' ').title()+'\n\n[Bundle index](../index.md)\n\n'
            for n in ns:t+=f"- [{n['id']} — {n['title']}]({PurePosixPath(n['path']).name}): {n['summary']}\n"
            out[group+'/index.md']=t
        # Non-concept directories have index documents but do not masquerade as concepts.
        for directory in ['schemas','catalog','work','examples','fixtures','tools','templates','generated','reports']:
            paths=sorted(p.name for p in (self.root/directory).glob('*') if p.is_file() and p.name not in ('index.md',))
            if directory=='generated':
                paths = sorted(set(paths) | {'index.json', 'command-reference.txt'})
            t='# '+directory.title()+'\n\n[Bundle index](../index.md). These files are not additional independent sources of normative authority.\n\n'
            for name in sorted(paths):t+=f'- [{name}]({name})\n'
            out[directory+'/index.md']=t
        # Reference publication, kept inside spec until explicitly published/bootstrap installed.
        cmds=read_json(self.root/'catalog/commands.json')
        t='# Planned DiskEd command reference\n\nGenerated from `spec/catalog/commands.json`; all listed commands are planned, not executable in this archive.\n\n'
        t+='Source digest: `'+digest_bytes((self.root/'catalog/commands.json').read_bytes())+'`.\n\n| Command | Semantic ID | Effect | Summary |\n|---|---|---|---|\n'
        for c in cmds['commands']:t+=f"| `disked {' '.join(c['words'])}` | `{c['id']}` | {c['effect']} | {c['summary']} |\n"
        out['generated/command-reference.txt']=t
        return out

    def index(self,check=False):
        expected=self.generated_files();stale=[]
        for rel,text in expected.items():
            path=safe_path(self.root,rel)
            if not path.exists() or read_text(path)!=text:
                stale.append(rel)
                if not check:
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8',newline='\n')
        if check and stale:raise SpecError('Generated files stale/missing: '+', '.join(stale))
        return {'files':len(expected),'changed':stale,'mode':'check' if check else 'regenerate'}

    def check(self,generated=True):
        errors=[]; checks=0
        def attempt(label,fn):
            nonlocal checks
            checks+=1
            try:fn()
            except Exception as exc:errors.append(label+': '+str(exc))
        # Path audit and basic JSON syntax for all tracked inputs; avoid ephemeral cache.
        allpaths=[]
        for p in sorted(self.root.rglob('*')):
            if any(x in ('__pycache__','.pytest_cache') for x in p.parts): continue
            if p.is_symlink():errors.append('Symlink in bundle: '+str(p));continue
            if p.is_file():allpaths.append(p)
        names={}
        reserved={'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}
        for p in allpaths:
            rel=p.relative_to(self.root).as_posix()
            attempt('safe path '+rel,lambda r=rel:safe_path(self.root,r,existing=True))
            key=rel.casefold()
            if key in names:errors.append('Case collision: '+rel+' / '+names[key])
            names[key]=rel
            for part in PurePosixPath(rel).parts:
                if part.split('.')[0].casefold() in reserved:errors.append('Reserved Windows path: '+rel)
            if p.suffix=='.json':attempt('JSON '+rel,lambda p=p:read_json(p))
        for id,c in self.concepts.items():
            def one(id=id,c=c):
                _,m,b,_=self.document(id)
                self.validate(SCHEMA_PREFIX+'frontmatter:1',m)
                if m['disked']['id']!=id:raise SpecError('ID mismatch')
                if m['title']!=c['title'] or m['description']!=c['summary'] or m['disked']['depends_on']!=c['depends_on']:raise SpecError('Concept catalog metadata drift')
                for dep in m['disked']['depends_on']:
                    if dep not in self.concepts:raise SpecError('Unresolved concept '+dep)
            attempt('concept '+id,one)
        registered={x['path'] for x in self.concepts.values()}
        for p in allpaths:
            rel=p.relative_to(self.root).as_posix()
            if p.suffix=='.md' and p.name not in ('index.md','log.md') and rel not in registered:
                errors.append('Unregistered concept Markdown: '+rel)
        attempt('concept dependency graph',lambda:acyclic({id:c['depends_on'] for id,c in self.concepts.items()},'concept graph'))
        for id,w in self.work.items():
            attempt('work '+id,lambda w=w:self.validate(SCHEMA_PREFIX+'work-unit:1',w))
            for c in w['context']:
                if c not in self.concepts:errors.append('Work context missing: '+c)
        def required_inputs():
            view=self.input_view()
            for input in view['inputs'].values():
                if not self.input_path(input['path']).is_file():raise SpecError('Missing required input '+input['path'])
                if not set(input['spec_ids'])<=self.concepts.keys():raise SpecError('Unknown required-input owner')
            for id in self.work:self.resolve_inputs(id,view)
        attempt('required input closure',required_inputs)
        attempt('work DAG',lambda:acyclic({id:w['dependencies'] for id,w in self.work.items()},'work graph'))
        decisions=unique_ids(read_json(self.root/'catalog/decisions.json')['decisions'],'decision')
        for w in self.work.values():
            for gate in w['decision_gates']:
                if gate not in decisions:errors.append('Unknown decision gate: '+gate)
        for catalog,field,sch in [('targets','targets','target'),('commands','commands','command'),('requirements','requirements','requirement'),('tests','tests','test-case')]:
            items=read_json(self.root/f'catalog/{catalog}.json')[field]
            attempt(catalog+' IDs',lambda i=items,c=catalog:unique_ids(i,c))
            for it in items:attempt(catalog+' '+it['id'],lambda x=it,s=sch:self.validate(SCHEMA_PREFIX+s+':1',x))
        attempt('component registry',self.component_registry)
        compositions=read_json(self.root/'catalog/compositions.json')['compositions']
        attempt('composition IDs',lambda:unique_ids(compositions,'composition'))
        for composition in compositions:
            attempt('composition '+composition['id'],lambda v=composition:self.validate(SCHEMA_PREFIX+'composition:1',v))
        amendments=read_json(self.root/'catalog/amendments.json')
        for collection in ('amendments','audit_findings','acceptance_designs'):
            rows=amendments[collection]
            attempt(collection+' IDs',lambda rows=rows:unique_ids(rows,collection))
            for row in rows:
                for id in row['spec_ids']:
                    if id not in self.concepts:errors.append('Unknown amendment spec: '+id)
                for id in row.get('work_ids',[]):
                    if id not in self.work:errors.append('Unknown amendment work: '+id)
        attempt('command registry',self.command_registry)
        attempt('requirements projection',self.requirements)
        for case in read_json(self.root/'catalog/validation-cases.json')['cases']:
            def run(case=case):
                value=read_json(safe_path(self.root,case['path'],existing=True))
                try:self.validate(case['schema'],value,case.get('semantic'));valid=True
                except SpecError:valid=False
                if valid!=case['valid']:raise SpecError('Unexpected validation result; expected '+str(case['valid']))
            attempt('schema example '+case['path'],run)
        for case in read_json(self.root/'fixtures/invocation.json')['cases']:
            attempt('invocation '+case['id'],lambda c=case:equal(route_invocation(c['inputs']),c['expected']))
        model=read_json(self.root/'catalog/journal-model.json');states=set(model['states'])
        for pair in model['transitions']:
            if not set(pair)<=states:errors.append('Unknown journal model state')
        if any(pair in model['transitions'] for pair in model['forbidden_transitions']):errors.append('Forbidden journal transition')
        reachable={model['initial']}
        for _ in states:
            reachable|={b for a,b in model['transitions'] if a in reachable}
        if reachable!=states:errors.append('Unreachable journal model state')
        # Ordinary relative Markdown link validation; outside-bundle links are disallowed here.
        for p in allpaths:
            if p.suffix!='.md':continue
            text=read_text(p)
            text=re.sub(r'```.*?```','',text,flags=re.S)
            for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^\s)]+)(?:\s+"[^"]*")?\)',text):
                dest=match.group(1).split('#')[0]
                if not dest or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',dest):continue
                raw=(p.parent/dest)
                try:
                    resolved=raw.resolve();resolved.relative_to(self.root)
                    if not resolved.exists():errors.append('Broken link '+p.relative_to(self.root).as_posix()+' -> '+dest)
                except ValueError:errors.append('Escaping link '+dest)
        # Source IDs are internal registry entries, not invented remote citations.
        source_ids={s['id'] for s in read_json(self.root/'references/sources.json')['sources']}
        for id in self.concepts:
            _,m,_,_=self.document(id)
            for src in m.get('sources',[]):
                if src.get('id') not in source_ids:errors.append('Unknown source ID '+str(src.get('id')))
        attempt('acceptance ledger',self.accepted)
        if generated:attempt('generated freshness',lambda:self.index(check=True))
        return {'schema':'org.disked.spec-check/1','status':'PASS' if not errors else 'FAIL','checks':checks,
                'concepts':len(self.concepts),'requirements':len(read_json(self.root/'catalog/requirements.json')['requirements']),
                'work_units':len(self.work),'schemas':len(self.schemas),'errors':errors,
                'scope':'Specification structure, local contracts, fixtures and tool projections only.',
                'not_validated':['DiskEd runtime','Windows binaries/GUI','physical storage','power-loss recovery','live AIDE CLI','Universal Setup integration','owner acceptance']}

    def command_registry(self):
        items=read_json(self.root/'catalog/commands.json')['commands'];spellings=set()
        unique_ids(items,'command')
        for command in items:
            self.validate(SCHEMA_PREFIX+'command:1',command)
            for word in [' '.join(command['words']),*command['aliases']]:
                if not re.fullmatch(r'[a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)*',word):
                    raise SpecError('Noncanonical command spelling: '+word)
                if word in spellings:raise SpecError('Duplicate command spelling: '+word)
                spellings.add(word)
            for id in command['spec_ids']:
                if id not in self.concepts:raise SpecError('Missing command spec: '+id)
            for key in ('request_schema','result_schema','parameter_schema'):
                if command[key] is not None and command[key] not in self.schemas:
                    raise SpecError('Unknown command schema: '+command[key])
            if command['syntax_status']=='unresolved':continue
            parameters=self.schemas[command['parameter_schema']]
            if parameters.get('type')!='object':raise SpecError('Command parameters must declare an object schema')
            properties=parameters.get('properties',{});bound=set();options=set();positions=set()
            for binding in command['argument_bindings']:
                parameter=binding['parameter']
                if parameter not in properties:raise SpecError('Unknown bound parameter: '+parameter)
                if parameter in bound:raise SpecError('Duplicate parameter binding: '+parameter)
                bound.add(parameter)
                for key,seen in [('option',options),('position',positions)]:
                    if key in binding:
                        if binding[key] in seen:raise SpecError('Duplicate argument '+key)
                        seen.add(binding[key])
                if binding['completion']=='schema-enum' and not isinstance(properties[parameter].get('enum'),list):
                    raise SpecError('Enum completion requires a parameter enum')
                if binding['completion']=='observed-id' and command['completion_policy']!='bounded-observations':
                    raise SpecError('Observed completion requires bounded observations')
            if bound!=set(properties):raise SpecError('Command parameter properties need explicit argument bindings')
            if positions and positions!=set(range(len(positions))):raise SpecError('Positional bindings must be contiguous from zero')
        return items

    def acceptance_projection(self):
        records=read_json(self.root/'work/acceptances.json')['records']
        rows=[];seen={};tips={};snapshots={};accepted=set()
        for rec in records:
            legacy=rec.get('schema')=='org.disked.acceptance/1'
            self.validate(SCHEMA_PREFIX+('acceptance:1' if legacy else 'acceptance-receipt:2'),rec)
            receipt=('legacy:'+digest_bytes(canonical(rec))[7:]) if legacy else rec['receipt_id']
            subject=rec['subject_id'];previous=tips.get(subject)
            if receipt in seen:raise SpecError('Duplicate receipt ID: '+receipt)
            if not legacy and rec['supersedes']!=previous:
                raise SpecError('Receipt must explicitly supersede the preceding receipt for its subject')
            row={'receipt_id':receipt,'subject_id':subject,'historical_validity':'unverified_legacy' if legacy else 'unverified','applicability':'not_current'}
            if previous:seen[previous]['applicability']='superseded'
            rows.append(row);seen[receipt]=row;tips[subject]=receipt
            if legacy:continue # Preserve unanchored v1 history; never grant from it.
            revision=rec['reviewed_revision']
            try:
                if revision not in snapshots:snapshots[revision]=GitSnapshot(self.root.parent,revision)
            except SpecError as exc:
                row.update(historical_validity='revision_unavailable',reason=str(exc));continue
            snapshot=snapshots[revision];view=self.input_view(snapshot)
            value=view['work'].get(subject) or view['decisions'].get(subject)
            if value is None or digest_bytes(canonical(value))!=rec['subject_digest']:
                raise SpecError('Receipt subject does not match reviewed revision: '+receipt)
            required=self.review_inputs(subject,view)
            supplied={f['path']:f for f in rec['input_files']}
            if len(supplied)!=len(rec['input_files']) or set(supplied)!=set(required):
                raise SpecError('Receipt reviewed input closure mismatch: '+receipt)
            snapshot.read_many(required)
            for path,item in supplied.items():
                self.input_path(path) # Reject ambiguous paths before any use.
                if digest_bytes(snapshot.read(path))!=item['sha256']:
                    raise SpecError('Receipt input differs from reviewed blob: '+path)
            row['historical_validity']='verified'
            if rec['decision']!='accept':
                row['applicability']='revoked' if rec['decision']=='revoke' else 'rejected';continue
            current=self.input_view();value=current['work'].get(subject) or current['decisions'].get(subject)
            if value is None or digest_bytes(canonical(value))!=rec['subject_digest']:
                row['applicability']='stale_subject';continue
            required_now=self.review_inputs(subject,current)
            if set(required_now)!=set(required):row['applicability']='stale_closure';continue
            if any(not self.input_path(path).is_file() or digest_bytes(self.input_path(path).read_bytes())!=item['sha256'] for path,item in supplied.items()):
                row['applicability']='stale_inputs';continue
            row['applicability']='current'
        for subject,receipt in tips.items():
            if seen[receipt]['applicability']=='current':accepted.add(subject)
        return {'accepted':sorted(accepted),'receipts':rows,'scope':'Local historical blob validity and current applicability, not reviewer authentication.'}

    def accepted(self):
        return set(self.acceptance_projection()['accepted'])

    def next_work(self):
        accepted=self.accepted();rows=[]
        for id,w in self.work.items():
            if id in accepted:continue
            blockers=[x for x in w['dependencies']+w['decision_gates'] if x not in accepted]
            rows.append({'id':id,'title':w['title'],'readiness':'ready_for_bounded_review_or_grant' if not blockers else 'blocked',
                         'blockers':blockers,'execution_authorized':False})
        return rows

    def context_ids(self, seeds, concepts=None):
        concepts=self.concepts if concepts is None else concepts
        ordered, active, seen = [], set(), set()
        def visit(id):
            if id in active: raise SpecError('Context dependency cycle: '+id)
            if id in seen: return
            if id not in concepts: raise SpecError('Unknown context concept: '+id)
            active.add(id)
            for dep in concepts[id]['depends_on']: visit(dep)
            active.remove(id); seen.add(id); ordered.append(id)
        for id in seeds: visit(id)
        return ordered

    def input_path(self,path):
        # Canonical names use spec/ even for a relocated --root spec-only bundle.
        if path.startswith('spec/'):return safe_path(self.root,path[5:])
        return safe_path(self.root.parent,path)

    def input_view(self,snapshot=None):
        paths=['spec/bundle.json','spec/catalog/concepts.json','spec/work/units.json','spec/catalog/decisions.json','spec/catalog/input-dependencies.json']
        if snapshot:snapshot.read_many(paths)
        values=[parse_json(snapshot.read(p).decode('utf-8')) if snapshot else read_json(self.input_path(p)) for p in paths]
        meta,concepts,work,decisions,registry=values
        self.validate(SCHEMA_PREFIX+'input-registry:1',registry)
        inputs=unique_ids(registry['inputs'],'required input')
        if len({i['path'] for i in inputs.values()})!=len(inputs):raise SpecError('Duplicate required input path')
        for item in inputs.values():self.input_path(item['path'])
        acyclic({id:i['depends_on'] for id,i in inputs.items()},'required input graph')
        instruction_names={'AGENTS.md','CLAUDE.md'}
        if snapshot:instructions=[p for p in snapshot.entries if PurePosixPath(p).name in instruction_names]
        else:
            instructions=[]
            for folder,dirs,files in os.walk(self.root.parent,followlinks=False):
                dirs[:]=sorted(d for d in dirs if d not in ('.git','.aide-local','.venv','__pycache__') and not (Path(folder)/d).is_symlink())
                for name in sorted(instruction_names & set(files)):
                    instructions.append((Path(folder)/name).relative_to(self.root.parent).as_posix())
        return {'meta':meta,'concepts':unique_ids(concepts['concepts'],'concept'),'work':unique_ids(work['units'],'work'),
                'decisions':unique_ids(decisions['decisions'],'decision'),'inputs':inputs,'always':registry['always'],'instructions':sorted(instructions)}

    def resolve_inputs(self,subject,view=None):
        view=self.input_view() if view is None else view
        work=view['work'].get(subject)
        if work is None and subject not in view['decisions']:raise SpecError('Unknown context subject '+subject)
        seeds=work['context'] if work else [view['decisions'][subject]['spec_id']]
        ids=self.context_ids(view['meta']['mandatory_context']+seeds,view['concepts'])
        inputs=view['inputs'];selected=set();files={}
        def visit(id):
            if id in selected:return
            if id not in inputs:raise SpecError('Unknown required input: '+id)
            for dep in inputs[id]['depends_on']:visit(dep)
            selected.add(id);item=inputs[id]
            files[item['path']]={key:item[key] for key in ('path','kind','delivery')}
        for id in view['always']+(work.get('required_inputs',[]) if work else []):visit(id)
        for id,item in inputs.items():
            if set(item['spec_ids'])&set(ids):visit(id)
        for id in ids:
            path='spec/'+view['concepts'][id]['path']
            files[path]={'path':path,'kind':'specification','delivery':'content'}
        scopes=[]
        for pattern in work['allowed_paths'] if work else ['spec/**']:
            prefix=re.split(r'[*?\[]',pattern,maxsplit=1)[0].rstrip('/')
            if prefix:self.input_path(prefix)
            scopes.append((prefix,any(c in pattern for c in '*?[')))
        for path in view['instructions']:
            parent=str(PurePosixPath(path).parent);parent='' if parent=='.' else parent+'/'
            applies=not parent or any(p.startswith(parent) for p in files)
            applies|=any(prefix.startswith(parent) or (glob and (parent.rstrip('/')==prefix or parent.startswith(prefix+'/'))) for prefix,glob in scopes)
            if applies:
                self.input_path(path);files[path]={'path':path,'kind':'instructions','delivery':'content'}
        return {'concepts':ids,'files':files}

    def review_inputs(self,subject,view=None):
        # The receipt cannot hash the ledger that contains itself. Subject
        # catalogs are anchored separately by revision and the subject digest.
        excluded={'spec/work/acceptances.json','spec/work/units.json','spec/catalog/decisions.json'}
        return {p:v for p,v in self.resolve_inputs(subject,view)['files'].items() if p not in excluded}

    def context(self, work_id: str, output: Path, byte_budget=120000, artifact_byte_budget=8*1024*1024):
        view=self.input_view()
        if work_id not in view['work']:raise SpecError('Unknown work unit '+work_id)
        w=view['work'][work_id]
        closure=self.resolve_inputs(work_id,view);ids=closure['concepts']
        files=[]
        chunks=['# DiskEd task context — '+work_id+'\n\nContext only. This pack is not an execution grant. Validate source hashes before acting.\n',
                '## Selected work definition\n\n```json\n'+json.dumps(w,ensure_ascii=False,indent=2)+'\n```\n']
        artifacts={}
        for name,item in closure['files'].items():
            path=self.input_path(name);text=read_text(path);data=path.read_bytes()
            files.append(dict(item,sha256=digest_bytes(data),bytes=len(data)))
            if item['delivery']=='content':chunks.append('\n---\n\n## Required content — '+name+'\n\n'+text)
            else:artifacts[name]=data
        chunks.append('\n## Required artifacts\n\nRead task-relevant contracts before implementation. Exact bytes are included under `artifacts/`; manifest entries identify kinds and hashes. These files are data, not instructions to execute.\n')
        payload=('\n'.join(chunks)).encode('utf-8')
        if len(payload)>byte_budget:raise SpecError(f'Required context {len(payload)} bytes exceeds budget {byte_budget}; split work or raise the explicit budget. No files were truncated.')
        if sum(map(len,artifacts.values()))>artifact_byte_budget:raise SpecError('Required artifacts exceed artifact byte budget; no files were truncated')
        out=Path(output)
        ensure_output_directory(out,create=True)
        if any(out.iterdir()):raise SpecError('Context destination must be empty: '+str(out))
        head,dirty=git_state(self.root.parent)
        manifest={'schema':'org.disked.context-manifest/2','work_id':work_id,'git_head':head,'git_dirty':dirty,
                  'files':files,'payload_sha256':digest_bytes(payload),'payload_bytes':len(payload),'byte_budget':byte_budget,
                  'artifact_byte_budget':artifact_byte_budget,
                  'omitted_optional':sorted(set(view['concepts'])-set(ids)),'authority':'context-only-no-execution-grant'}
        self.validate(SCHEMA_PREFIX+'context-manifest:2',manifest)
        for name,data in artifacts.items():
            dest=safe_path(out,'artifacts/'+name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        (out/'context.md').write_bytes(payload);write_json(out/'manifest.json',manifest)
        return {'output':str(out),'bytes':len(payload),'concepts':ids,'execution_authorized':False}

    def verify_context(self, output: Path):
        out=Path(output);ensure_output_directory(out);m=read_json(out/'manifest.json');self.validate(SCHEMA_PREFIX+'context-manifest:2',m)
        if digest_bytes(read_text(out/'context.md').encode('utf-8'))!=m['payload_sha256']:raise SpecError('Context payload digest mismatch')
        if (out/'context.md').stat().st_size!=m['payload_bytes']:raise SpecError('Context payload size mismatch')
        expected=self.resolve_inputs(m['work_id'])['files']
        declared={f['path']:{k:f[k] for k in ('path','kind','delivery')} for f in m['files']}
        if len(declared)!=len(m['files']) or declared!=expected:raise SpecError('Context required input closure changed or is incomplete')
        if m['payload_bytes']>m['byte_budget'] or sum(f['bytes'] for f in m['files'] if f['delivery']=='artifact')>m['artifact_byte_budget']:raise SpecError('Context exceeds declared budgets')
        for f in m['files']:
            p=self.input_path(f['path'])
            if digest_bytes(p.read_bytes())!=f['sha256']:raise SpecError('Context source changed: '+f['path'])
            if p.stat().st_size!=f['bytes']:raise SpecError('Context source size mismatch')
            if f['delivery']=='artifact':
                copied=safe_path(out,'artifacts/'+f['path'],existing=True)
                if digest_bytes(copied.read_bytes())!=f['sha256']:raise SpecError('Context artifact changed: '+f['path'])
        current,_=git_state(self.root.parent)
        if m['git_head'] is not None and current!=m['git_head']:raise SpecError('Context Git head changed')
        return {'status':'PASS','work_id':m['work_id'],'scope':'Declared task-input closure and included artifact freshness, not execution approval.'}

    def aide_export(self, output: Path):
        out=Path(output);ensure_output_directory(out,create=True)
        if any(out.iterdir()):raise SpecError('AIDE export destination must be empty')
        count=0
        for id,w in self.work.items():
            v={'apiVersion':'aide.disked-projection/v1','kind':'WorkUnit',
               'metadata':{'id':id,'createdAt':self.meta['generated_at'],'sourcePath':'spec/work/units.json',
                           'producer':{'name':'disked-specctl','version':self.meta['version']},
                           'compatibility':{'schemaVersion':'1','protocolVersion':'1','minReaderVersion':'1','minWriterVersion':'1','featureFlags':['disked-non-authorizing-projection']}},
               'spec':{'task_id':id,'title':w['title'],'work_type':'check' if id=='DE-W000' else 'build',
                       'authorizes_implementation':False,'check_only':id=='DE-W000','acceptance_review':id=='DE-W000',
                       'implementation_scope':'See spec/work/units.json for exact outputs. Separate grant required.',
                       'stop_state':'needs_review','predecessors':w['dependencies'],'dependencies':w['decision_gates'],
                       'scope':{'allowed_paths':w['allowed_paths'],'forbidden_paths':w['forbidden_paths'],
                                'forbidden_operations':w['forbidden_operations'],'read_only_review_paths':['spec/**']},
                       'validation':{'commands':[{'command':c,'status':'NOT_RUN'} for c in w['validation_commands']]},
                       'evidence_requirements':w['acceptance'],'explicit_non_capabilities':['physical_device_access','elevation','release_signing','automatic_promotion','execution_authority']},
               'status':{'phase':'planned','result':'NOT_RUN','validated':False,'validation_errors':[],
                         'validation_warnings':['Projection shape checked locally; full pinned AIDE runtime/CLI integration not executed.']}}
            self.validate(SCHEMA_PREFIX+'aide-workunit-projection:1',v)
            write_json(out/(id+'.json'),v);count+=1
        return {'records':count,'execution_authorized':False,'upstream_cli_verified':False}

    def impact(self,paths):
        ids=set();mods=read_json(self.root/'catalog/project-graph.json')['modules']
        view=self.input_view();closures={id:self.resolve_inputs(id,view) for id in view['work']}
        matched=[];unmatched=[];owners={};affected_work=set()
        for raw in paths:
            path=raw.replace('\\','/')
            self.input_path(path)
            path_ids=set();path_owners=set()
            if path.startswith('spec/'):
                rel=path[5:]
                path_ids|={id for id,c in self.concepts.items() if c['path']==rel}
                path_owners.update(path_ids)
            for m in mods:
                if path in m.get('file_paths',[]) or any(path.startswith(pre.rstrip('/')+'/') or path==pre.rstrip('/') for pre in m['path_prefixes']):
                    path_ids.update(m['spec_ids']);path_owners.add(m['id'])
            for input in view['inputs'].values():
                if input['path']==path:path_ids.update(input['spec_ids']);path_owners.update(input['spec_ids'])
            for work,closure in closures.items():
                if path in closure['files']:
                    affected_work.add(work);path_owners.add(work)
            if path_owners:matched.append(path);owners[path]=sorted(path_owners)
            else:unmatched.append(path)
            ids.update(path_ids)
        # Expand reverse semantic dependencies conservatively.
        changed=True
        while changed:
            new={id for id,c in self.concepts.items() if set(c['depends_on']) & ids}-ids
            changed=bool(new);ids|=new
        reqs,_=self.requirements()
        affected_work.update(id for id,closure in closures.items() if set(closure['concepts'])&ids)
        return {'paths':paths,'matched_paths':matched,'unmatched_paths':unmatched,'matched_owners':owners,
                'unknown_impact':bool(unmatched),'spec_ids':sorted(ids),
                'work_ids':sorted(affected_work),
                'test_ids':[t for r in reqs if r['spec'] in ids for t in r['test_ids']],
                'review_required':True,'scope':'Conservative routing; not automatic test adequacy.'}

    def bootstrap(self,repo_root:Path,apply=False):
        root=Path(repo_root);ensure_output_directory(root,create=apply);root=root.resolve()
        mapping=read_json(self.root/'templates/bootstrap-map.json')['files'];prepared=[]
        for item in mapping:
            source=safe_path(self.root,item['source'],existing=True)
            dest=safe_path(root,item['destination'])
            if dest.exists():raise SpecError('Bootstrap refuses existing file: '+str(dest))
            prepared.append((source,dest))
        # All destinations preflighted before any product file write. This is not a concurrent filesystem transaction.
        if apply:
            for source,dest in prepared:
                safe_path(root,dest.relative_to(root).as_posix())
                dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as f:f.write(source.read_bytes())
        return {'mode':'applied' if apply else 'preview','files':[str(d.relative_to(root)) for _,d in prepared],
                'overwrites':False,'remote_writes':False}

    def manifest(self,verify=False):
        path=self.root/'manifest.json'
        files=[]
        # Path ordering differs on Windows (case folded) and POSIX. Use the
        # serialized relative path so a byte-identical bundle travels intact.
        for p in sorted(self.root.rglob('*'), key=lambda p:p.relative_to(self.root).as_posix()):
            if not p.is_file() or any(x in ('__pycache__','.pytest_cache') for x in p.parts):continue
            rel=p.relative_to(self.root).as_posix()
            if rel=='manifest.json' or rel.endswith('.tmp'):continue
            safe_path(self.root,rel,existing=True)
            files.append({'path':rel,'bytes':p.stat().st_size,'sha256':digest_bytes(p.read_bytes())})
        value={'schema':'org.disked.spec-manifest/1','bundle_version':self.meta['version'],
               'excluded':['manifest.json','**/__pycache__/**','**/.pytest_cache/**','**/*.tmp'],
               'authenticity':'not-a-signature','files':files}
        if verify:
            if read_json(path)!=value:raise SpecError('Bundle manifest mismatch: source changed, missing or extra files. Regenerate only after legitimate reviewed edits.')
        else:write_json(path,value)
        return {'status':'PASS','mode':'verify' if verify else 'generate','files':len(files),'bytes':sum(f['bytes'] for f in files)}

def ensure_output_directory(path: Path,create=False):
    path=Path(path)
    # Reject symlink ancestors before resolving them.
    for p in [path]+list(path.parents):
        if p.is_symlink():raise SpecError('Symlink output directory: '+str(p))
    if path.exists() and not path.is_dir():raise SpecError('Output is not a directory: '+str(path))
    if create:path.mkdir(parents=True,exist_ok=True)

def equal(a,b):
    if a!=b:raise SpecError('Expected '+repr(b)+', got '+repr(a))

def route_invocation(i):
    """Pure policy oracle. Does not inspect or manipulate a real console."""
    front=i.get('frontend','auto');fmt=i.get('format','human');interactive=i.get('interactive','auto')
    terminal=i.get('terminal','none');gui=i.get('gui_available',False);display=i.get('display',False)
    def result(f,inter,reason):return {'frontend':f,'format':fmt,'interactive':inter,'reason':reason}
    if front not in ('auto','cli','tui','gui','plain') or fmt not in ('human','json','ndjson') or interactive not in ('auto','yes','no'):
        return {'error':'invalid_argument'}
    if fmt in ('json','ndjson'):
        if front in ('gui','tui') or interactive=='yes':return {'error':'argument_conflict'}
        return result('cli',False,'machine-output')
    if front in ('gui','tui') and interactive=='no':return {'error':'argument_conflict'}
    # Prompt permission is independent of persistent-shell selection. A separate
    # explicitly available prompt channel can be used with redirected results.
    prompt=i.get('prompt_channel', terminal!='none' and i.get('stdin') not in ('pipe','file','absent','invalid')
                 and i.get('stdout') not in ('pipe','file','absent','invalid'))
    if front not in ('gui','tui') and interactive=='yes' and not prompt:
        return {'error':'interaction_unavailable'}
    if front!='auto':
        if front=='gui' and not (gui and display):return {'error':'frontend_unavailable'}
        if front=='tui' and terminal=='none':return {'error':'frontend_unavailable'}
        return result(front,front in ('gui','tui') or interactive=='yes','explicit-frontend')
    if i.get('command'):return result('cli',interactive=='yes','explicit-command')
    if interactive=='no':return result('cli',False,'noninteractive-request')
    if interactive=='yes':return result('cli',True,'explicit-interaction')
    if i.get('desktop') and gui and display:return result('gui',True,'desktop-activation')
    if i.get('stdin') in ('pipe','file') or i.get('stdout') in ('pipe','file'):
        return result('cli',False,'redirected-stream')
    if terminal=='limited':return result('plain',False,'limited-terminal')
    if terminal=='capable' and i.get('console_owner')=='caller':return result('tui',True,'interactive-terminal')
    if terminal=='capable':return result('plain',False,'ambiguous-launch')
    return result('plain',False,'no-interactive-host')

def git_state(root):
    try:
        env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')
        prefix=['git','--no-optional-locks','-c','core.fsmonitor=false','-c','core.untrackedCache=false','-C',str(root)]
        head=subprocess.run(prefix+['rev-parse','HEAD'],capture_output=True,text=True,timeout=5,env=env)
        if head.returncode:return None,None
        dirty=subprocess.run(prefix+['status','--porcelain'],capture_output=True,text=True,timeout=5,env=env)
        return head.stdout.strip(),bool(dirty.stdout) if not dirty.returncode else None
    except (OSError,subprocess.TimeoutExpired):return None,None

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT,help='Specification root, not repository root')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor');sub.add_parser('check');sub.add_parser('next');sub.add_parser('acceptance-status')
    ix=sub.add_parser('index');ix.add_argument('--check',action='store_true')
    sh=sub.add_parser('show');sh.add_argument('id')
    se=sub.add_parser('search');se.add_argument('query');se.add_argument('--limit',type=int,default=8)
    cx=sub.add_parser('context');cx.add_argument('--work',required=True);cx.add_argument('--output',type=Path,required=True);cx.add_argument('--byte-budget',type=int,default=120000)
    cx.add_argument('--artifact-byte-budget',type=int,default=8*1024*1024)
    vc=sub.add_parser('verify-context');vc.add_argument('directory',type=Path)
    ae=sub.add_parser('aide-export');ae.add_argument('--output',type=Path,required=True)
    im=sub.add_parser('impact');im.add_argument('paths',nargs='+')
    bs=sub.add_parser('bootstrap');bs.add_argument('--root',dest='repo_root',type=Path,default=Path('.'));bs.add_argument('--apply',action='store_true')
    sub.add_parser('manifest');sub.add_parser('verify-manifest')
    args=p.parse_args(argv)
    try:
        if args.command=='doctor':
            result={'python':sys.version.split()[0],'intended_minimum':'3.10','packages':{}}
            for name in ['PyYAML','jsonschema']:
                try:result['packages'][name]=importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:result['packages'][name]='MISSING'
            result['ready']=sys.version_info>=(3,10) and 'MISSING' not in result['packages'].values()
            print(json.dumps(result,indent=2));return 0 if result['ready'] else 2
        b=Bundle(args.root)
        if args.command=='show':print(b.document(args.id)[3],end='');return 0
        if args.command=='check':
            result=b.check();print(json.dumps(result,indent=2));return 0 if result['status']=='PASS' else 1
        if args.command=='index':result=b.index(args.check)
        elif args.command=='next':result={'work':b.next_work(),'execution_authorized':False}
        elif args.command=='acceptance-status':result=b.acceptance_projection()
        elif args.command=='context':result=b.context(args.work,args.output,args.byte_budget,args.artifact_byte_budget)
        elif args.command=='verify-context':result=b.verify_context(args.directory)
        elif args.command=='aide-export':result=b.aide_export(args.output)
        elif args.command=='impact':result=b.impact(args.paths)
        elif args.command=='bootstrap':result=b.bootstrap(args.repo_root,args.apply)
        elif args.command=='manifest':result=b.manifest()
        elif args.command=='verify-manifest':result=b.manifest(True)
        elif args.command=='search':
            terms=re.findall(r'[\w-]+',args.query.casefold());rows=[]
            for id,c in b.concepts.items():
                text=b.document(id)[3].casefold();score=sum(text.count(t) for t in terms)
                score+=sum(10 for t in terms if t in (c['title']+' '+id).casefold())
                if score:rows.append({'id':id,'path':'spec/'+c['path'],'title':c['title'],'summary':c['summary'],'score':score})
            result={'results':sorted(rows,key=lambda x:(-x['score'],x['id']))[:max(1,min(args.limit,50))],
                    'method':'Deterministic keyword routing, not semantic completeness.'}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (SpecError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({'status':'ERROR','error':str(exc)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__':
    raise SystemExit(main())
