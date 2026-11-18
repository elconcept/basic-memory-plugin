---
title: Decision
type: schema
entity: Decision
version: 1
schema:
  decision: string, actual choice
  rationale?: string, reason for the choice
  alternative?(array): string, other options considered
  consequence?(array): string, outcomes
  context?: string, cause and background
  affects?(array): Entity, related notes
  supersedes?: Entity, earlier replaced decision
settings:
  validation: warn
  frontmatter:
    status?(enum, lifecycle): [open, accepted, superseded, rejected]
    decided?: string, ISO decision timestamp
    project?: string, project
---
# Decision

Use a `- [decision] ...` observation and preserve rationale and alternatives.
