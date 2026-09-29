---
tags: [migration, issue-tracking]
doc_type: reference
project: whoseonfirst
source: manual
aliases: ["WHO to WOF mapping", "WhoseOnFirst issue migration"]
created: "2026-06-09"
updated: "2026-06-09"
---

# Issue Tracking Migration — WHO → WOF

On **2026-04-27** WhoseOnFirst migrated issue tracking from the DocVault `WHO-` prefix to
Plane with the `WOF-` prefix.

- **Plane project:** <https://plane.lbruton.cc/lbruton/projects/a5951628-b52b-4224-bee6-87b513fa6e7b/>
- **Historical max (DocVault):** `WHO-54`
- New issues are created via `/issue` (dispatches on `.specflow/config.json` `issue_backend`)
  or directly via `mcp__plane__create_issue`.

## Open-Issue Renumbering

Issues that were open at migration time were recreated in Plane and renumbered:

| Old (DocVault) | New (Plane) | Summary |
|----------------|-------------|---------|
| WHO-43 | WOF-1 | Admin UI for Twilio credentials — DB storage |
| WHO-44 | WOF-2 | Migrate all env-based config to Admin UI settings |
| WHO-47 | WOF-3 | Sign session cookies (privilege-escalation fix) |
| WHO-51 | WOF-4 | Commit `.coderabbit.yaml` configuration |
| WHO-53 | WOF-5 | Version-tracking baseline (version.lock, /release flow) |
| WHO-54 | WOF-6 | Live Twilio integration test |

Closed and cancelled `WHO-` issues were **not** recreated in Plane.

> Source: salvaged from PR #39 (`chore/onboard-plane`) before it was closed as superseded
> by PR #41, which had already updated `CLAUDE.md` to the terse `Prefix WOF` form. The
> `DocVault/Archive/Issues-Pre-Plane/WhoseOnFirst/` path referenced in that PR was never
> actually created, so this table is the canonical record of the renumbering.

## Notes for Reviewers

Git commit messages and the `WHO-43-admin-ui-twilio-credentials` spec folder still carry
the legacy `WHO-` prefix (immutable history). Bot reviewers (CodeRabbit, Copilot) may flag
`WHO-` references for a few PRs — these are expected false positives, not action items.
