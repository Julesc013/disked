# Disposable profile preflight

This is a prerequisite experiment, not a Disk Management observation. Keep the
four UI tuples unrun until an actual MMC reference is collected. The existing
native/API records remain bound to their original source and execution profile.

The new `--windows-ui-profile` mode runs the current ordinary-worker controls and
native byte-port controls, then gives only the fresh owned actor a temporary
ProfileList entry pointing at its capped `R:` profile. It copies regular default
profile files with entry/byte bounds and no links, omitting unused `.lnk` shell
shortcuts. Windows' default hardlinked shortcuts are not needed by this fixture;
other hardlinked files remain refused. No shell or shortcut is executed. The guest coordinator loads
that hive using [LoadUserProfileW](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-loaduserprofilew).
The restricted probe must resolve profile/known folders within that profile,
keep temporary output in managed work, and write a nonce independently read from
the owned hive. This private fixture arrangement is experimental, not a supported
profile-relocation feature or administrative UI qualification.

Retire the job before unloading the hive; verify its exact SID and profile path
before deleting that profile. Account/image retirement refuses an unresolved
profile journal. No shared account, global profile policy, UAC, VM setting,
foreground desktop or product protection is changed. No MMC process or test
medium is admitted by this mode. Its existing private desktop is retained.

Before execution, source/AST/template/Windows PowerShell 5.1 preparation passed.
The five new copy controls reject per-file/aggregate byte overflow, excess
entries and hard links, and preserve ordinary nested bytes. The complete tooling
suite ran 246 tests with one skip; 15 affected bundle tests, 1,328 structural
checks and manifest verification passed. These are host tooling checks; native
profile execution remains unverified until the following guest receipt exists.
The first copy-control failure and its correction are retained compactly. The
first guest attempt at `8187b03b` refused default hardlinked shortcuts before
creating a profile key or loading a hive; owned account/image cleanup passed.
The next source explicitly omits those unused assets and adds a corresponding
selection test; it retains the hive-hardlink rejection control.
