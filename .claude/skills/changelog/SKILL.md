---
name: changelog
description: Generate a Keep a Changelog entry from git commits
---

# /changelog - Generate Changelog Entry

## Purpose

Generate a Keep a Changelog entry matching the existing CHANGELOG.md style, if available.

## Usage

```
/changelog [version]
```

Version is optional — suggest one based on the changes (patch for fixes, minor for features, major for breaking changes).

## Process

1. **Find the last tag and get commits**

   ```
   git describe --tags --abbrev=0
   git log --pretty=format:'%s' <tag>..HEAD
   ```

2. **Categorize using Keep a Changelog sections**

   - `### Features` — new capabilities
   - `### Changed` — breaking or notable behavior changes
   - `### Enhancements` — improvements to existing features
   - `### Bug Fixes` — things that were broken
   - `### Removed` — removed features (rare)

3. **Write entries in a consistent voice**

   Match the existing style:

   - Start with imperative verb or noun phrase
   - Bold key concepts on first mention: `**Overlay commit model for file writes**:`
   - Sub-bullets for details when a feature has multiple parts
   - Technical but accessible — users are developers

   Examples:

   - `Fix login regression: use OAuth2 instead of deprecated token flow`
   - `Improve CLI help with quick start guide and clearer description`
   - `**Remote file sync**: sync_remote() now supports conflict detection`

4. **Skip internal-only changes**

   Omit: CI tweaks, refactoring without user impact, dependency bumps (unless security-related)

5. **Output format**

   ```markdown
   ## [x.y.z] - YYYY-MM-DD

   ### Features

   - **Feature name**: Description of what users can now do

   ### Bug Fixes

   - Fix specific thing that was broken
   ```

6. **Prepend to CHANGELOG.md**

   If CHANGELOG.md doesn't exist, create it with this header:

   ```markdown
   # Changelog

   All notable changes to this project will be documented in this file.

   The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
   and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
   ```

   If an `## [Unreleased]` section exists, insert after it. Otherwise, insert after the file header (title and any preamble), before the first version entry.

## Notes

- Keep sections in order: Features → Changed → Enhancements → Bug Fixes → Removed
- Omit empty sections
- Date format: YYYY-MM-DD
- If unsure about version bump, ask
