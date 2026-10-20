"""Shared typed task-input closure; identifiers are independent of file paths."""
from pathlib import PurePosixPath
import re


def context_ids(seeds,concepts,error=ValueError):
    ordered,active,seen=[],set(),set()
    def visit(id):
        if id in active:raise error('Context dependency cycle: '+id)
        if id in seen:return
        if id not in concepts:raise error('Unknown context concept: '+id)
        active.add(id)
        for dep in concepts[id]['depends_on']:visit(dep)
        active.remove(id);seen.add(id);ordered.append(id)
    for id in seeds:visit(id)
    return ordered


def resolve_inputs(subject,view,validate_path,error=ValueError):
    work=view['work'].get(subject)
    if work is None and subject not in view['decisions']:raise error('Unknown context subject '+subject)
    seeds=work['context'] if work else [view['decisions'][subject]['spec_id']]
    ids=context_ids(view['meta']['mandatory_context']+seeds,view['concepts'],error)
    inputs=view['inputs'];selected=set();active=set();files={}
    def visit(id):
        if id in active:raise error('Required input dependency cycle: '+id)
        if id in selected:return
        if id not in inputs:raise error('Unknown required input: '+id)
        active.add(id)
        for dep in inputs[id]['depends_on']:visit(dep)
        active.remove(id);selected.add(id);item=inputs[id];validate_path(item['path'])
        files[item['path']]={key:item[key] for key in ('path','kind','delivery')}
    for id in view['always']+(work.get('required_inputs',[]) if work else []):visit(id)
    for id,item in inputs.items():
        if set(item['spec_ids'])&set(ids):visit(id)
    for id in ids:
        path='spec/'+view['concepts'][id]['path'];validate_path(path)
        files[path]=dict(path=path,kind='specification',delivery='content')
    scopes=[]
    for pattern in work['allowed_paths'] if work else ['spec/**']:
        prefix=re.split(r'[*?\[]',pattern,maxsplit=1)[0].rstrip('/')
        if prefix:validate_path(prefix)
        scopes.append((prefix,any(c in pattern for c in '*?[')))
    for path in view['instructions']:
        parent=str(PurePosixPath(path).parent);parent='' if parent=='.' else parent+'/'
        applies=not parent or any(p.startswith(parent) for p in files)
        applies|=any(prefix.startswith(parent) or (glob and (parent.rstrip('/')==prefix or parent.startswith(prefix+'/'))) for prefix,glob in scopes)
        if applies:validate_path(path);files[path]=dict(path=path,kind='instructions',delivery='content')
    return dict(concepts=ids,files=files)
