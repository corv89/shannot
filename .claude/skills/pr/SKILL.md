---
name: pr
description: Commit changes, bump version, update changelog, and open a PR
---

# /pr - Prepare and Submit Changes

## Purpose

Commit changes to a feature branch, bump version if needed, update changelog, and open a PR.

## Before Starting

- Check for uncommitted changes: `git status --porcelain`
- Ensure tests pass: `make test` or equivalent
- Confirm current branch (create one if on main)

## Process

1. **Create or verify feature branch**

   If on main, create a branch from the work context:
   ```
   git checkout -b <descriptive-branch-name>
   ```

2. **Stage and commit changes**

   Use the user's git identity (never sign as Claude, no Co-authored-by).
   Write conventional commit messages:
   - `feat: add remote file sync`
   - `fix: resolve timeout on large files`

3. **Bump version if warranted**

   - Bug fixes → patch
   - New features → minor
   - Breaking changes → major

   Update version in pyproject.toml (or equivalent).

4. **Update CHANGELOG.md**

   Use /changelog skill to generate entry if changes are user-facing.

5. **Push and create PR**

   ```
   git push -u origin <branch>
   gh pr create --fill
   ```

   PR description should summarize changes. Link issues if referenced in commits.

## Notes

- Don't add "Signed-off-by" or "Co-authored-by: Claude" trailers
- Ask before force-pushing
- If tests fail, stop and report
