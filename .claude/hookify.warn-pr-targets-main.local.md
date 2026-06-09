---
name: warn-pr-targets-main
enabled: true
event: bash
pattern: gh\s+pr\s+create\s+.*(?:-B|--base)\s+main
action: warn
---

WARNING: PR targets 'main' branch.

WhoseOnFirst uses 'dev' as the integration branch. PRs should target 'dev' unless
this is an explicit release merge (dev → main). Dependabot PRs also need retargeting.

Correct: gh pr create --base dev
