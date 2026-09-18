# Getting started

## Requirements

Reading the specification requires only a Markdown viewer or browser. Running the specification tools requires a modern coordinator host with Python 3.10 or later and the dependencies in `spec/tools/requirements.txt`. This Python requirement is not the DiskEd product's eventual Windows/DOS runtime requirement.

Create a local virtual environment and install the declared dependencies:

```text
python -m venv .venv
```

Activate it using your shell's normal procedure, then:

```text
python -m pip install -r spec/tools/requirements.txt -c spec/tools/constraints-tested.txt
python spec/tools/specctl.py doctor
python spec/tools/specctl.py check
python -m unittest discover -s spec/tools/tests -v
python spec/tools/specctl.py verify-manifest
```

The constraints record the generator environment's tested versions, not an offline wheelhouse or authenticated supply-chain lock. Check dependency availability before an air-gapped deployment. No model API, vector service or running AIDE service is required.

## Choose the first work

```text
python spec/tools/specctl.py next
python spec/tools/specctl.py show DE-080
python spec/tools/specctl.py context --work DE-W000 --output .aide-local/context/review
```

Review the context, the current owner request and the decision register. `DE-W000` ratifies or corrects the proposed baseline. The next fake-provider vertical slice has no physical storage access.

## Spec-only import

The spec-only ZIP extracts to `spec/`. It does not overwrite root instructions. To add the supplied root entrypoints and these documentation pages, preview first:

```text
python spec/tools/specctl.py bootstrap --root .
python spec/tools/specctl.py bootstrap --root . --apply
```

The bootstrap command refuses existing destinations and symlink paths. Resolve conflicts manually; there is no overwrite flag. The repository-bootstrap ZIP already includes those files, so do not run bootstrap again over that layout.

## What is not present

There is no DiskEd native executable, filesystem executor, elevated broker or live AIDE scheduler in this archive. Example product requests are fixtures, not commands to execute on workstation drives. Windows, hardware, recovery and installation claims require later evidence.
