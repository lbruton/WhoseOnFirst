---
tags: []
doc_type: reference
project: whoseonfirst
source: migrated
aliases: ["Memento Taxonomy"]
created: "2025-11-09"
updated: "2026-06-09"
migrated_from: "repo:docs/TAXONOMY.md"
---

# Memento Knowledge Graph Taxonomy for WhoseOnFirst

## Overview

This document defines the tagging taxonomy and naming conventions for the WhoseOnFirst Memento knowledge graph. It's adapted from HexTrackr's proven system but simplified for our smaller project scope.

## Core Principles

1. **Every entity MUST have tags** - No untagged entities
2. **Tags enable multi-dimensional search** - Complement PROJECT:DOMAIN:TYPE classification
3. **Consistency over creativity** - Use existing tags before creating new ones
4. **Project isolation** - All entities tagged with `project:whoseonfirst`
5. **Temporal awareness** - Include week-based tags for tracking

## Entity Naming Convention

### Classification Pattern: PROJECT:DOMAIN:TYPE

**PROJECT**: `WHOSEONFIRST`

**DOMAIN** (Second Level):
- `DEVELOPMENT` - Active development work
- `WORKFLOW` - Process patterns and workflows
- `BACKEND` - Server/API/scheduler work
- `FRONTEND` - UI/UX work
- `DATABASE` - Data layer, migrations
- `SCHEDULER` - APScheduler jobs and automation
- `DEPLOYMENT` - Docker, production deployment
- `DOCUMENTATION` - Docs and guides
- `TESTING` - Test suites and quality

**TYPE** (Third Level):
- `SESSION` - Work sessions
- `INSIGHT` - Learned patterns
- `PATTERN` - Reusable solutions
- `DECISION` - Architectural choices
- `ISSUE` - Problems/bugs
- `BREAKTHROUGH` - Major discoveries

## Tag Taxonomy

### 1. Project Tag (Required)

Every entity MUST have: `project:whoseonfirst`

### 2. Category Tags

Work type classification:
- `backend` - Server, API, scheduler, business logic
- `frontend` - UI/UX, HTML, JavaScript, CSS
- `database` - Schema, queries, migrations
- `scheduler` - APScheduler jobs, cron tasks
- `docker` - Container, deployment, compose files
- `workflow` - Process improvements
- `documentation` - Docs, guides, README files
- `testing` - Unit, integration tests

### 3. Impact Tags

Change significance:
- `feature` - New functionality
- `enhancement` - Improvements to existing features
- `bug-fix` - Bug corrections
- `critical-bug` - System-breaking issues
- `performance` - Speed/efficiency improvements
- `security-fix` - Security patches

### 4. Workflow Tags

Current status:
- `completed` - Finished work
- `in-progress` - Active development
- `blocked` - Waiting on dependencies
- `needs-review` - Requires validation

### 5. Learning Tags

Knowledge type:
- `lesson-learned` - Mistakes to avoid
- `pattern` - Repeatable solutions
- `breakthrough` - Major discoveries
- `best-practice` - Recommended approaches
- `anti-pattern` - What not to do
- `reusable` - Cross-project applicable

### 6. Temporal Tags

Time-based markers:
- `week-XX-YYYY` - Week number (e.g., `week-45-2025`)
- `vX.X.X` - Version tags (e.g., `v1.0.0`)
- `YYYY-MM` - Month tags (e.g., `2025-11`)

### 7. Linear Integration Tags

Issue tracking:
- `linear:WHO-X` - Linear issue reference (e.g., `linear:WHO-2`)
- `linear:WHO-XXX` - For multi-digit issue IDs

### 8. WhoseOnFirst-Specific Tags

Domain-specific markers:
- `rotation-algorithm` - Circular rotation logic
- `sms-notification` - Twilio SMS functionality
- `schedule-generation` - Schedule creation
- `auto-renewal` - Auto-renewal feature
- `team-management` - Team member CRUD
- `shift-configuration` - Shift setup
- `apscheduler` - Scheduler-specific work
- `twilio` - Twilio integration

## Required Observations (In Order)

Every entity MUST include these observations in this exact order:

1. `TIMESTAMP: ISO 8601 format` - When created
2. `ABSTRACT: One-line summary` - Quick overview
3. `SUMMARY: Detailed description` - Full context
4. `[TYPE]_ID: Unique identifier` - SESSION_ID, INSIGHT_ID, etc.

## Search Strategy

### Use `mcp__memento__search_nodes` for:
- Exact ID matching (SESSION_ID, INSIGHT_ID)
- Specific tag queries (`linear:WHO-2`, `week-45-2025`)
- Entity type filters (`WHOSEONFIRST:DEVELOPMENT:SESSION`)
- Status checks (`completed`, `in-progress`)

### Use `mcp__memento__semantic_search` for:
- Conceptual queries ("docker workflow patterns")
- Natural language searches ("how to handle scheduler jobs")
- Cross-cutting themes ("auto-renewal implementation")
- Discovery queries ("rotation algorithm insights")

## Tagging Examples

### Session Entity

```javascript
// Create entity
mcp__memento__create_entities([{
  name: "Session: WHOSEONFIRST-AUTORENEWAL-20251109-120000",
  entityType: "WHOSEONFIRST:DEVELOPMENT:SESSION",
  observations: [
    "TIMESTAMP: 2025-11-09T12:00:00.000Z",
    "ABSTRACT: Auto-renewal feature implementation",
    "SUMMARY: Implemented schedule auto-renewal system...",
    "SESSION_ID: WHOSEONFIRST-AUTORENEWAL-20251109-120000"
  ]
}]);

// Add tags
mcp__memento__add_observations({
  observations: [{
    entityName: "Session: WHOSEONFIRST-AUTORENEWAL-20251109-120000",
    contents: [
      "TAG: project:whoseonfirst",
      "TAG: linear:WHO-2",
      "TAG: backend",
      "TAG: scheduler",
      "TAG: feature",
      "TAG: completed",
      "TAG: week-45-2025",
      "TAG: auto-renewal",
      "TAG: apscheduler"
    ]
  }]
});
```

### Insight Entity

```javascript
// Create entity
mcp__memento__create_entities([{
  name: "Insight: Docker-First Development Workflow",
  entityType: "WHOSEONFIRST:WORKFLOW:PATTERN",
  observations: [
    "TIMESTAMP: 2025-11-09T18:00:00.000Z",
    "ABSTRACT: Docker rebuild checkpoints for code changes",
    "SUMMARY: WhoseOnFirst development requires Docker container rebuild...",
    "INSIGHT_ID: WHOSEONFIRST-INSIGHT-20251109-180000"
  ]
}]);

// Add tags
mcp__memento__add_observations({
  observations: [{
    entityName: "Insight: Docker-First Development Workflow",
    contents: [
      "TAG: project:whoseonfirst",
      "TAG: workflow",
      "TAG: docker",
      "TAG: pattern",
      "TAG: best-practice",
      "TAG: reusable",
      "TAG: week-45-2025"
    ]
  }]
});
```

## Query Patterns

### Find Work by Linear Issue
```
"linear:WHO-2" - All work on WHO-2
"linear:WHO-2 completed" - Completed WHO-2 tasks
```

### Find by Feature Area
```
"auto-renewal apscheduler" - Auto-renewal scheduler work
"rotation-algorithm pattern" - Rotation algorithm patterns
"twilio sms-notification" - SMS notification code
```

### Time-Based Queries
```
"week-45-2025 project:whoseonfirst" - This week's work
"v1.0.0 feature" - Version 1.0.0 features
```

### Cross-Project Insights
```
"reusable pattern docker" - Docker patterns applicable to other projects
"breakthrough scheduler" - Scheduler breakthroughs
```

## Maintenance Rules

### Weekly Cleanup
1. Update temporal tags (week numbers)
2. Archive completed sprint tags
3. Consolidate similar tags

### Entity Lifecycle
- Active work: Tagged with current week
- Completed work: Tagged `completed` + version
- Archived insights: Keep indefinitely with `reusable` tag

---

**Version**: 1.0.0
**Last Updated**: 2025-11-09
**Authority**: This document defines the official Memento taxonomy for WhoseOnFirst
**Adapted From**: HexTrackr TAXONOMY.md
