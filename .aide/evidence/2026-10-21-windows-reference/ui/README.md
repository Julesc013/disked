# UI preparation

The [disposable profile proof](REVIEW.md) passed at `10f4173f`, with actual
restricted profile/known-folder/HKCU observations and complete owned cleanup.
It does not qualify an administrative MMC reference or complete any UI tuple.
The inventory below predates that proof.

The installed MMC, Disk Management and UI Automation components are identified in
[inventory.json](inventory.json). The default-profile measurement completed at
130 entries/2,756,221 logical bytes, skipping 17 links; allocation was not measured.
No MMC window, UI profile, attachment or UI reference observation ran during
that inventory.

`query user Agents` returned exit 1 despite output containing an active Agents
console/session 3 line. Preserve both facts. Verify the actual session/token with
Windows APIs before dispatch; this is not evidence of a credential failure and
does not justify an account reset, UAC change or login prompt.

Demonstrate bounded disposable profile/output paths and an isolated or explicitly
leased desktop before the four real UI observations. A denied nonadministrator
preflight does not substitute for the intended operational Disk Management
reference. Keep native product-worker and administrative reference roles separate.
