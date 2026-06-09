---
name: warn-docker-compose-no-dev
enabled: true
event: bash
pattern: docker.compose\s+up(?!.*-f\s+docker-compose\.dev\.yml)
action: warn
---

WARNING: docker-compose up without specifying docker-compose.dev.yml.

The default docker-compose.yml is for PRODUCTION (Portainer GitOps). For local development:
  docker-compose -f docker-compose.dev.yml up -d --build

Without -f docker-compose.dev.yml, SMS_MOCK_MODE is not set and REAL SMS will be sent.
