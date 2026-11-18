---
title: Task
type: schema
entity: Task
version: 1
schema:
  description: string, what to do
  status?(enum, lifecycle): [active, blocked, done, abandoned]
  assigned_to?: string, owner
  steps?(array): string, planned steps
  current_step?: integer, current one-based index
  context?: string, continuation state
  started?: string, date
  completed?: string, date
  blockers?(array): string, blockers
  parent_task?: Task, parent task relation
settings:
  validation: warn
---
# Task

Put queryable lifecycle status in frontmatter and corresponding observations.
