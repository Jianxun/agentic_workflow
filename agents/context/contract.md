# Project Overview

This repository develops an agentic workflow system. The agents under `agents/` define roles, contracts, and task flow for collaboration.

# System Boundaries / Components

- Role definitions in `agents/roles/`.
- Shared project context in `agents/context/`.
- Task scratchpads in `agents/scratchpads/`.
- ADRs in `agents/adr/` when decisions warrant it.

# Interfaces & Data Contracts

- Task definitions and metadata are stored in YAML under `agents/context/` using the schemas documented in `agents/roles/architect.md`.
- Status for tasks is stored only in `agents/context/tasks_state.yaml`.

# Invariants

- Task status lives only in `agents/context/tasks_state.yaml`.
- `agents/context/` files are the source of truth for project state.
- ADRs are append-only and listed in the decision log.

# Verification Protocol

- None defined yet.

# Decision Log

- 2026-01-16: Initialize agents context scaffolding.
