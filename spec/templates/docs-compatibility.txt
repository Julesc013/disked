# Compatibility and support claims

The [target catalog](../spec/catalog/targets.json) describes intended profiles. **No target in this baseline is a qualified DiskEd product build.** Windows XP, 7, 10 and 11 are the near-term focus; other systems remain explicit planned profiles.

A target profile separates OS/API floor, architecture, executable format, toolkit, provider closure, distribution properties and evidence. “One entrypoint,” “one downloaded file,” “self-contained” and “zero extraction” are different properties.

A capability is scoped to a particular operation, provider version, filesystem, topology, execution environment and test evidence. “NTFS support” does not imply every NTFS resize or recovery operation works. An old OS being out of vendor support and DiskEd qualifying a bounded function on it are different questions.

The product can preserve an unknown structure or inspect an image even when it cannot mutate the underlying filesystem. Unsupported and offline-only outcomes are useful results, not missing buttons to conceal.

See [Windows profiles](../spec/platforms/windows-targets.md), [DOS/Carbon/OS2](../spec/platforms/dos-carbon-os2.md), and [other hosts and media](../spec/platforms/other-hosts-and-media.md).
