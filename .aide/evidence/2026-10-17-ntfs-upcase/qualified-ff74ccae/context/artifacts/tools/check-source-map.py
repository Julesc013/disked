"""Check that the contributor source map names every current source file once."""
import argparse
from collections import Counter
from pathlib import Path
import re

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    root=parser.parse_args().root.resolve()
    text=(root/'docs/source-map.md').read_text(encoding='utf-8')
    links=Counter(re.findall(r'\]\(\.\./(source/[^)]+)\)',text))
    actual={p.relative_to(root).as_posix() for p in (root/'source').rglob('*') if p.is_file()}
    missing=sorted(actual-set(links));obsolete=sorted(set(links)-actual)
    repeated=sorted(p for p,n in links.items() if n!=1)
    if missing or obsolete or repeated:
        raise SystemExit(f'Source map mismatch: missing={missing}; obsolete={obsolete}; repeated={repeated}')
    print(f'Source map covers all {len(actual)} current files once; future locations are proposals, not file-existence claims.')

if __name__=='__main__':main()
