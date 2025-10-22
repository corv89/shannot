# Shannot Planning Directory

This directory contains planning documents, design notes, and development tracking for Shannot. These files are **not** user-facing documentation - they're for maintainers and contributors.

## Structure

```
plans/
├── README.md                  # This file
├── ROADMAP.md                 # Current priorities and timeline
├── REMOTE.md                  # Remote execution planning notes
├── MCP.md                     # MCP integration planning notes
├── LLM.md                     # LLM integration planning notes
└── archive/                   # Completed planning docs
    ├── architecture-executors.md
    ├── implementation-plan-executors.md
    └── executor-implementation-summary.md
```

## Active Planning Docs

### ROADMAP.md
**Purpose**: Single source of truth for what to work on next.

**Contents**:
- Current status
- Prioritized features (Tier 1/2/3)
- Timeline estimates
- Success metrics
- Next steps

**When to update**: Weekly, or when priorities change.

### REMOTE.md
**Purpose**: Planning notes for remote execution features.

**Contents**:
- SSH executor status and next steps
- Configuration system design
- Security considerations
- Future enhancements (HTTP agent)

**When to update**: When working on remote execution features.

### MCP.md
**Purpose**: Planning notes for MCP integration.

**Contents**:
- Phase 1 completion status
- Phase 2+ enhancements (per-command tools, rate limiting)
- MCP + remote integration plans
- Pydantic-AI integration notes

**When to update**: When working on MCP features.

### LLM.md
**Purpose**: High-level LLM integration strategy.

**Contents**:
- MCP vs Pydantic-AI comparison
- Use case examples and decision tree
- Architecture diagrams
- Future agent API design

**When to update**: When making strategic decisions about LLM integration.

## Archive

Contains completed planning docs from Phase 1 implementations:
- `architecture-executors.md` - Executor design (now in code)
- `implementation-plan-executors.md` - Executor implementation plan (complete)
- `executor-implementation-summary.md` - What was built (complete)

**When to move to archive**: When implementation is complete and docs are no longer referenced.

## User-Facing Docs

User and developer documentation lives in `docs/`:
- `docs/installation.md` - Installation guide
- `docs/usage.md` - CLI usage
- `docs/profiles.md` - Profile configuration
- `docs/api.md` - Python API reference
- etc.

**Rule**: If users need it, it goes in `docs/`. If maintainers need it, it goes in `plans/`.

## Git

This entire `plans/` directory is **gitignored** (since 2025-10-21).

**Why**: Planning docs are local working notes, not part of the public repository. The source code and user docs in `docs/` are the public interface.

**Exception**: Some teams may want to track planning docs in git. If so, remove `plans/` from `.gitignore` and commit selectively.

## Workflow

### Planning a New Feature
1. Check `ROADMAP.md` for priorities
2. Create/update relevant planning doc (`REMOTE.md`, `MCP.md`, etc.)
3. Write design notes, code sketches, open questions
4. Start implementation
5. Update `ROADMAP.md` status as you progress

### Completing a Feature
1. Mark complete in `ROADMAP.md`
2. Update relevant planning doc with final status
3. Consider moving detailed implementation docs to `archive/`
4. Write user documentation in `docs/` if needed

### Weekly Review
1. Review `ROADMAP.md` priorities
2. Update status for in-progress items
3. Adjust timeline if needed
4. Identify next week's focus

## Questions?

If you're not sure where something belongs:
- **User needs to know** → `docs/`
- **Developer needs to understand** → Code comments + docstrings
- **Maintainer needs to plan** → `plans/`
- **Historical reference** → `plans/archive/`

---

**Maintained by**: Shannot Team
**Last Updated**: 2025-10-21
