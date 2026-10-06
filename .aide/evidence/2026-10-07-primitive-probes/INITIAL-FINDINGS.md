# Primitive control findings

The initial GCC 15.2.0 x64 and MSVC 19.44 x64 builds each passed 411 independent
arithmetic/representation/text cases on the current Windows host. The initial
MSVC 2017 Hostx64/x86 invocation failed with C1356 because its adjacent tool path
did not supply mspdbcore.dll. The existing same-version Hostx86/x86 installation
contains the needed DLL and built successfully without installation or a DLL copy.
That executable passed the same 411 cases with a reported 32-bit pointer. Both
compiler invocations and the failure log are retained. No expected result changed.
Compiler-banner-only invocations of cl.exe return their normal nonzero no-input
exit; those are version observations, not failed compilation or test cases.

The first full specification suite ran 171 tests, with three errors and one
failure in context-fixture setup and two existing Windows symlink skips. The
complete evolving DE-W010 context exceeded the old 180000-byte fixture allowance.
The valid-context integrity/determinism/destination fixtures now explicitly allow
260000 bytes. Their assertions are unchanged; the independent 100-byte refusal
and no-truncation case is unchanged and passes. No runtime context budget or
required content was reduced. The private probe input owners are DE-051 and the
explicit DE-W018 required-input set; they do not declare a product runtime ABI.
The focused seven context tests passed before rerunning the full suite.

Read-only discovery found GCC, NASM, MSVC 2022/2017 and Windows SDK directories.
No period 8086/Win16/OS2 compiler was found in the examined installation roots and
PATH. VirtualBox 7.2.6 has registered Windows 3.1/98 fixtures, but their guest
contents, installed systems, launch behavior and media rights were not qualified.
No VM was booted or changed, and no disk image was mounted. Presence of a named
VM or ISO does not count as a successful historical launch.

The C90 controls have no device/path argument or storage implementation. Their
stdio loader/runtime behavior is measured only on this modern host. The product
parser, historical terminal/keyboard/code-page behavior, 16-bit-int compilation,
8086 CPU audit, Win16 NE, Win9x and OS/2 loader admission remain not_run.
