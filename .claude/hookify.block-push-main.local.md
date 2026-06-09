---
name: block-push-main
enabled: true
event: bash
pattern: git\s+push\b.*\smain(?:\s|$)
action: block
---

BLOCKED: Direct push to main triggers Portainer GitOps production deployment.

WhoseOnFirst workflow: feature → dev → main (via PR only).
Push to a feature branch and create a PR targeting dev instead.
Only merge dev → main on explicit "ship" or "release" from the user.
