"""One-off reviewed source migration; never executes native fixtures."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    registry=ROOT/'spec/catalog/input-dependencies.json'
    records=json.loads(registry.read_bytes())
    changes=[]
    for area in ('frontend','images','evidence','operation','recovery'):
        for path in sorted((ROOT/'tests'/area).glob('*.py')):
            before=path.read_bytes();tree=ast.parse(before)
            parents=[n for n in ast.walk(tree) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div)
                     and isinstance(n.right,ast.Constant) and n.right.value=='.aide-local']
            if not parents:continue
            lines=before.splitlines(keepends=True);offsets=[0]
            for line in lines:offsets.append(offsets[-1]+len(line))
            def span(node):return offsets[node.lineno-1]+node.col_offset,offsets[node.end_lineno-1]+node.end_col_offset
            edits=[(*span(n),b'managed_parent()') for n in parents]
            constructors=[]
            for n in ast.walk(tree):
                if not (isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and
                        isinstance(n.func.value,ast.Name) and n.func.value.id=='tempfile' and
                        n.func.attr=='TemporaryDirectory'):continue
                kws={k.arg:k.value for k in n.keywords}
                if (n.args or set(kws)!= {'prefix','dir'} or not isinstance(kws['dir'],ast.Name)
                        or kws['dir'].id not in ('scratch','parent')):continue
                a,b=span(kws['prefix']);value=b'managed_directory(prefix='+before[a:b]+b')'
                edits.append((*span(n),value));constructors.append(n.lineno)
            pathlib=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='pathlib'
                     and any(a.name=='Path' and a.asname is None for a in n.names)]
            insertion=offsets[max(n.end_lineno for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)))]
            imports='\n'+('from pathlib import Path\n' if not pathlib else '')
            if not any(isinstance(n,ast.Import) and any(a.name=='sys' and not a.asname for a in n.names) for n in tree.body):imports+='import sys\n'
            imports+="sys.path.insert(0,str(Path(__file__).resolve().parents[1]))\nfrom support.tempdir import fixture_parent as managed_parent, managed_directory\n"
            edits.append((insertion,insertion,imports.encode()))
            after=before
            for start,end,value in sorted(edits,reverse=True):after=after[:start]+value+after[end:]
            guards={
              'tests/images/test_fat_worker.py':('scratch.resolve().is_relative_to(root.resolve())','scratch.resolve()==managed_parent().resolve()'),
              'tests/evidence/test_file_export.py':('scratch.is_relative_to(a.root.resolve())','scratch==managed_parent().resolve()'),
              'tests/operation/test_worker_directory.py':('scratch.is_relative_to(root)','scratch==managed_parent().resolve()')}
            relative=path.relative_to(ROOT).as_posix()
            if relative in guards:
                old,new=guards[relative];assert after.count(old.encode())==1
                after=after.replace(old.encode(),new.encode(),1)
            final=ast.parse(after)
            methods=lambda t:[n.name for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')]
            assertions=lambda t:sum(isinstance(n,ast.Assert) for n in ast.walk(t))
            assert methods(tree)==methods(final) and assertions(tree)==assertions(final)
            constants=lambda t:Counter((type(n.value).__name__,repr(n.value)) for n in ast.walk(t)
                if isinstance(n,ast.Constant) and n.value!='.aide-local')
            removed=Counter()
            for node in parents:removed.update(constants(node))
            assert constants(tree)-removed+Counter({('int','0'):1,('int','1'):1})==constants(final),path
            rows=[r for r in records['inputs'] if r['path']==relative];assert len(rows)==1,relative
            deps=rows[0]['depends_on'];assert 'tests/support/tempdir.py' not in deps
            deps.append('tests/support/tempdir.py')
            path.write_bytes(after)
            changes.append(dict(path=relative,before_sha256=digest(before),after_sha256=digest(after),
                managed_parent_expressions=len(parents),managed_directory_constructors=constructors,
                assertion_count=assertions(tree),test_methods_unchanged=methods(tree)))
    assert len(changes)==35 and sum(c['managed_parent_expressions'] for c in changes)==38
    registry.write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
    (HERE/'migration.json').write_text(json.dumps(dict(scope='Scratch parent/constructor and three parent-location guards only; native fixture oracles and deadlines unchanged',
        native_tests_run=False,changes=changes),indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
