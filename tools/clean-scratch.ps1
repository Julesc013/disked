#Requires -Version 5.1
<#
Inspect this checkout's .aide-local directory; deletion is explicitly opt-in.
Run from outside .aide-local after stopping its workers. This is housekeeping,
not a quota, process terminator or protection against a concurrently hostile writer.
Nested repositories, registered worktrees, links and read-only files are preserved.
Exit 0: complete; 2: partial/skipped; 1: refused/error. No archives or logs are made.
#>
[CmdletBinding()]
param([switch]$Delete, [switch]$WorkersStopped)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Scratch = Join-Path $Repo '.aide-local'

try {
    if ($Delete -and -not $WorkersStopped) {
        throw 'Stop this checkout''s workers first; deletion requires -WorkersStopped.'
    }
    $current = [IO.Path]::GetFullPath((Get-Location).Path)
    if ([string]::Equals($current, $Scratch, [StringComparison]::OrdinalIgnoreCase) -or
        $current.StartsWith($Scratch + [IO.Path]::DirectorySeparatorChar,
                            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Run from outside .aide-local; the caller must not occupy the cleanup target.'
    }
    # Check every ancestor before asking Git to inspect the checkout.
    $ancestor = $Scratch
    while ($ancestor) {
        try { $attributes = [IO.File]::GetAttributes($ancestor) }
        catch [IO.FileNotFoundException] { $attributes = 0 }
        catch [IO.DirectoryNotFoundException] { $attributes = 0 }
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing a linked/reparse ancestor: $ancestor"
        }
        $parent = [IO.Directory]::GetParent($ancestor)
        $ancestor = if ($null -eq $parent) { $null } else { $parent.FullName }
    }
    Get-Command git -ErrorAction Stop | Out-Null
    $top = @(& git --no-optional-locks -C $Repo rev-parse --show-toplevel)
    if ($LASTEXITCODE -ne 0 -or $top.Count -ne 1 -or
        -not [string]::Equals([IO.Path]::GetFullPath($top[0]), $Repo,
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Cannot establish the exact repository root; no cleanup attempted.'
    }
    $tracked = @(& git --no-optional-locks -C $Repo ls-files -- .aide-local)
    if ($LASTEXITCODE -ne 0 -or $tracked.Count -ne 0) {
        throw 'Cannot establish that .aide-local has no tracked files; no cleanup attempted.'
    }
    # Preserve registered worktree roots even if their .git marker is missing.
    $worktreeOutput = @(& git --no-optional-locks -C $Repo worktree list --porcelain -z)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate registered worktrees.' }
    $protected = @((($worktreeOutput -join "`n") -split '\x00') |
        Where-Object { $_.StartsWith('worktree ') } |
        ForEach-Object { [IO.Path]::GetFullPath($_.Substring(9)) } |
        Where-Object { $_.StartsWith($Scratch + [IO.Path]::DirectorySeparatorChar,
                                    [StringComparison]::OrdinalIgnoreCase) })
    if (-not ('DiskEdScratchCleanup' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;

public sealed class DiskEdScratchReport {
    public string Mode;
    public string Target;
    public long EligibleFiles;
    public long LogicalBytes;
    public long RemovedDirectories;
    public long SkippedEntries;
    public long VolumeFreeBefore;
    public long VolumeFreeAfter;
    public List<string> Skipped = new List<string>();
}

public sealed class DiskEdScratchCleanup {
    private string root;
    private bool delete;
    private HashSet<string> protectedRoots;
    private DiskEdScratchReport report;

    private void Skip(string path, string reason) {
        report.SkippedEntries++;
        if (report.Skipped.Count < 20) report.Skipped.Add(path + ": " + reason);
    }

    private void Check(string path) {
        string full = Path.GetFullPath(path);
        if (!String.Equals(full, root, StringComparison.OrdinalIgnoreCase) &&
            !full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new IOException("Path is outside the scratch root");
        // Recheck existing ancestors immediately before acting. Stopped writers
        // remain essential: this is not a race-proof handle-based sandbox.
        string parent = Path.GetDirectoryName(full);
        while (parent != null) {
            if ((File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Linked ancestor: " + parent);
            parent = Path.GetDirectoryName(parent);
        }
    }

    private bool Exists(string path) {
        try { File.GetAttributes(path); return true; }
        catch (FileNotFoundException) { return false; }
        catch (DirectoryNotFoundException) { return false; }
    }

    private void Visit(string path, int depth) {
        try {
            Check(path);
            if (depth > 128) { Skip(path, "depth limit"); return; }
            FileAttributes attributes = File.GetAttributes(path);
            if ((attributes & FileAttributes.ReparsePoint) != 0) {
                Skip(path, "link/reparse point; not followed"); return;
            }
            if (protectedRoots.Contains(path)) {
                Skip(path, "registered worktree; review separately"); return;
            }
            if ((attributes & FileAttributes.Directory) != 0) {
                if (Exists(Path.Combine(path, ".git")) ||
                    (Exists(Path.Combine(path, "HEAD")) && Exists(Path.Combine(path, "objects")) &&
                     Exists(Path.Combine(path, "config")))) {
                    Skip(path, "repository/worktree; review separately"); return;
                }
                // Streaming enumeration avoids materializing giant directories.
                foreach (string child in Directory.EnumerateFileSystemEntries(path)) Visit(child, depth + 1);
                if (delete && path != root) {
                    Check(path);
                    if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                        throw new IOException("Directory became a link");
                    using (IEnumerator<string> entries = Directory.EnumerateFileSystemEntries(path).GetEnumerator()) {
                        if (entries.MoveNext()) return;
                    }
                    Directory.Delete(path, false); // Empty directories only.
                    report.RemovedDirectories++;
                }
            } else {
                if ((attributes & FileAttributes.ReadOnly) != 0) {
                    Skip(path, "read-only file; attributes unchanged"); return;
                }
                long size = new FileInfo(path).Length;
                if (delete) {
                    Check(path);
                    if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                        throw new IOException("File became a link");
                    File.Delete(path);
                }
                report.EligibleFiles++;
                report.LogicalBytes += size;
            }
        } catch (Exception error) { Skip(path, error.Message); }
    }

    public DiskEdScratchReport Run(string scratch, string[] protectedPaths, bool remove) {
        root = Path.GetFullPath(scratch);
        delete = remove;
        protectedRoots = new HashSet<string>(protectedPaths, StringComparer.OrdinalIgnoreCase);
        report = new DiskEdScratchReport { Mode = remove ? "delete" : "inspect", Target = root };
        DriveInfo volume = new DriveInfo(Path.GetPathRoot(root));
        report.VolumeFreeBefore = volume.AvailableFreeSpace;
        if (Exists(root)) {
            if ((File.GetAttributes(root) & FileAttributes.Directory) == 0)
                throw new IOException("Scratch root is not a directory");
            Visit(root, 0);
        }
        report.VolumeFreeAfter = volume.AvailableFreeSpace;
        return report;
    }
}
'@
    }
    $report = ([DiskEdScratchCleanup]::new()).Run($Scratch, [string[]]$protected, [bool]$Delete)
    $report | ConvertTo-Json -Depth 4
    # LogicalBytes is NOT allocated storage. Other projects can change volume free
    # space concurrently; its before/after difference is not exclusive attribution.
    if ($report.SkippedEntries -gt 0) { exit 2 }
    exit 0
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
