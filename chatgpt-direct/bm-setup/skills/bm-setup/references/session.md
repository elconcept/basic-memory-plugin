---
title: Session
type: schema
entity: Session
version: 1
schema:
  summary?: string, one-paragraph summary
  context?(array): string, state needed to resume
  next_step?(array): string, exact next action
  decision?(array): string, decisions
  problem?(array): string, blockers
  produced?(array): Entity, linked notes
settings:
  validation: warn
  frontmatter:
    project: string, project
    started: string, ISO timestamp
    ended?: string, optional checkpoint time
    status?(enum, lifecycle): [open, resumed, closed]
    session_id?: string, host identifier
    agent?: string, ChatGPT or other harness
    capture?(enum, kind): [extractive, deliberate, summarized]
---
# Session

Resume checkpoint. Store observations as categorized lines and link only existing notes.
