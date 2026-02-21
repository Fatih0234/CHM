# CHM Pull Request Workflow

Use one issue and one PR per SpecKit task.

## Required Rules

- Every task must have one GitHub issue.
- Every task branch must start from `main` and target `main`.
- Every PR must include `Closes #<issue-number>` in the body.
- Every PR must implement one primary task only.

## Task-Scoped Flow

1. Create or confirm the task issue (`CHM T###: ...`).
2. Sync local `main`:
   - `git checkout main`
   - `git pull --ff-only origin main`
3. Create a task branch:
   - `git checkout -b codex/task/T###-short-slug`
4. Implement the task and run acceptance checks from `tasks.md`.
5. Commit with `CHM T###: <task title>`.
6. Push branch:
   - `git push -u origin codex/task/T###-short-slug`
7. Create PR with base branch `main` and include:
   - `Closes #<issue-number>`
8. Merge PR after checks pass, then sync local `main` again.

## Verification

- Confirm PR body includes `Closes #<issue-number>`.
- Confirm PR base branch is `main`.
- Confirm related issue auto-closes after merge.
