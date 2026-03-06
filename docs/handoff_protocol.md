# Handoff Protocol

Status: active operating rule
Last updated: 2026-03-06

## Purpose

This document defines how agents keep the project state current without turning documentation into a blocking chore.

The rule is simple:

- major state changes update canonical docs
- all meaningful work leaves a short append-only trail

## Canonical Documents vs Work Log

Use the documents for different purposes:

- `docs/status.md`: current project snapshot
- `docs/roadmap.md`: active phase and sequencing
- `docs/dev_setup.md`: environment, commands, and verification workflow
- `docs/work_log.md`: append-only record of meaningful work sessions

Do not force every task to rewrite every document.

## Non-Blocking Update Rule

At the end of any meaningful task, the agent must do at least one of:

1. update a canonical document if project state actually changed
2. append a short entry to `docs/work_log.md`

This keeps handoff quality high without making documentation heavy.

## When To Update `docs/status.md`

Update `docs/status.md` when any of the following changes:

- what is implemented
- what is not implemented
- the current active engineering target
- the canonical data source
- major known gaps

If none of those changed materially, do not rewrite `status.md`.

## When To Update `docs/roadmap.md`

Update `docs/roadmap.md` when:

- a phase starts or completes
- the active priority changes
- the planned sequencing changes

If the task does not affect phase state or priorities, leave `roadmap.md` alone.

## When To Update `docs/dev_setup.md`

Update `docs/dev_setup.md` when:

- a new command becomes part of normal workflow
- new dependencies are introduced
- validation or run instructions change
- package setup or entrypoints change

## `docs/work_log.md` Format

Each meaningful task should append a compact entry with:

- date
- summary
- files changed
- verification performed
- next recommended step

Keep entries short.
The work log is for continuity, not essays.

## Minimum Acceptable Handoff

If time is tight or the task is small, the minimum acceptable handoff is:

- append one concise `docs/work_log.md` entry

If the task changes project state, also update the relevant canonical doc.

## Anti-Patterns

Avoid:

- rewriting `status.md` after every tiny edit
- leaving meaningful work with no trace
- hiding important state changes only in the work log
- updating roadmap language without changing actual priorities

## Rule Of Thumb

- work log for session continuity
- status for current truth
- roadmap for phase truth
- setup for operational truth
