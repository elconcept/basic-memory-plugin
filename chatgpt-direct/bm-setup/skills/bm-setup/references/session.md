---
title: Session
type: schema
entity: Session
version: 1
schema:
  summary?: string, one-paragraph what-happened this session
  context?(array): string, key context needed to resume after memory loss
  next_step?(array): string, explicit cursor for the next session
  decision?(array): string, decisions surfaced during the session
  problem?(array): string, problems hit — including attempted-and-rejected approaches
  produced?(array): Entity, notes created or updated during the session
settings:
  validation: warn
  frontmatter:
    project: string, the Basic Memory project this session belongs to
    started: string, when the session began (ISO timestamp)
    ended?: string, when the session was checkpointed
    status?(enum, lifecycle of the checkpoint): [open, resumed, closed]
    cwd?: string, the working directory the session ran in
    username?: string, operating-system user that created the checkpoint
    hostname?: string, host that created the checkpoint
    session_id?: string, exact host-provided session identifier (pair with agent)
    agent?: string, agent harness identifier such as tau or claude-code or codex
    tau_session_id?: string, legacy Tau session identifier (read compatibility only)
    claude_session_id?: string, legacy Claude Code session identifier (read compatibility only)
    capture?(enum, how this checkpoint was produced): [extractive, deliberate, summarized]
---

# Session

A SessionNote is a resume checkpoint. Basic Memory integrations write these at their supported lifecycle boundaries or on an explicit checkpoint request. It records what the session was doing so the next session can pick up where this one left off.

## What goes in a SessionNote
- summary — what happened.
- context / next_step — current state and next action.
- decision / problem — choices and dead-ends.
- produced — relations to notes created or changed.
