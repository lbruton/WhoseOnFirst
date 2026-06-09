---
name: block-prod-db-restore
enabled: true
event: bash
pattern: Nextcloud/Backups/whoseonfirst|docker\s+cp.*\.db.*whoseonfirst-dev|backups/whoseonfirst\.db.*whoseonfirst-dev
action: block
---

BLOCKED: Restoring production backups to dev environment is prohibited (WHO-49 guardrail).

The Opus incident showed AI agents will overwrite dev data with production backups if not blocked.

Correct procedure:
- Let first-boot auto-seed (admin/Admin123!, viewer/User123!)
- Or import sanitized seed: `~/whoseonfirst-dev-data/backups/dev-seed-sanitized.stvault`
- NEVER use files from `~/Nextcloud/Backups/whoseonfirst/` or production `.db` files
