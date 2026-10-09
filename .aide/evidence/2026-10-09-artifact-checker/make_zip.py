"""Owned local test recipe; not an admitted release producer or installer.

Run only after independently inventorying and reviewing quiescent staging.
Does not read the expected inventory and never extracts or executes contents.
"""
from pathlib import Path
import sys,zipfile
stage=Path(sys.argv[1]);archive=Path(sys.argv[2])
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(stage.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(stage).as_posix())
print('Created owned local ZIP fixture from staging, independent of inventory')
