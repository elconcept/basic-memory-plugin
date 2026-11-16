---
title: Decision
type: schema
entity: Decision
version: 1
schema:
  decision: string, the choice that was made
  rationale?: string, why this choice over the alternatives
  alternative?(array): string, options that were considered and not taken
  consequence?(array): string, what this decision commits us to
  context?: string, the situation that prompted the decision
  affects?(array): Entity, work or notes this decision bears on
  supersedes?: Entity, a prior decision this one replaces
settings:
  validation: warn
  frontmatter:
    status?(enum, lifecycle of the decision): [open, accepted, superseded, rejected]
    decided?: string, when the decision was made (ISO timestamp)
    project?: string, the Basic Memory project this decision belongs to
---

# Decision

A durable record of a meaningful choice with rationale, alternatives and consequences. Find with `bm_search(filters={"type":"decision","status":"open"},project=...)`.
