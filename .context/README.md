# `.context/` — WhoseOnFirst Foundation Docs

In-repo, version-controlled foundation documentation. This is the **source of truth**
for project architecture, standards, and workflow — it travels with the code (and to any
downstream GitLab mirror), unlike the previously gitignored `docs/` folder it replaces.

Foundation docs live here (agent-facing, tracked). Human/product-facing material and
long-term research live in DocVault (`/Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/`).

## Documents

| File | Purpose | Read before… |
| --- | --- | --- |
| [architecture.md](architecture.md) | System design: FastAPI app, APScheduler jobs, SQLite/SQLAlchemy data layer, Twilio integration, 8-page frontend. | Touching `src/` structure, scheduler, or data model. |
| [technical-stack.md](technical-stack.md) | Stack decisions and rationale: FastAPI, APScheduler, SQLAlchemy, Tabler.io/Bootstrap 5, Docker. | Adding a dependency or evaluating a stack change. |
| [code-patterns.md](code-patterns.md) | Recurring implementation patterns: ORM/transaction conventions, phone masking, validation, error handling. | Writing any new `src/` code. |
| [authentication.md](authentication.md) | Auth system design — Argon2id hashing (OWASP 2025 params), session model. | Touching auth, sessions, or password handling. |
| [rpi-process.md](rpi-process.md) | The project's Research → Plan → Implement workflow (override of the global spec-workflow). | Starting any non-trivial feature or `/sketch`/`/spec`/`/gsd` work. |

## Conventions

- These docs describe **intended** design. Freshness against live code is audited
  separately (devops context-drift skill) — treat a claim as authoritative only after
  cross-checking the named source when it matters.
- Update the relevant doc in the same PR as a behavior-affecting change to the area it
  covers.
- Provenance: migrated from the gitignored `docs/` tree on 2026-06-09 (WOF-11). Original
  filenames were `docs/planning/architecture.md`, `docs/planning/technical-stack.md`,
  `docs/reference/code-patterns.md`, `docs/planning/AUTHENTICATION_SPEC.md`, and
  `docs/RPI_PROCESS.md`.
