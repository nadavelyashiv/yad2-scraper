---
name: ship-pr
description: >-
  Use this skill when the user asks to automate the procedure of creating a GitHub issue, branching, committing, and opening a PR for their current uncommitted changes.
---

# Ship PR Workflow

This skill automates the process of wrapping up a task into a PR. Execute these steps carefully.

## Steps

1.  **Analyze Changes**: Review the recent conversation context and current uncommitted changes (`git status`, `git diff`).
2.  **Create Issue**:
    *   Formulate a title and detailed body for the GitHub issue based on the task context and file changes.
    *   Run `gh issue create --title "<title>" --body "<body>"`.
    *   Parse the output to get the Issue ID (e.g., `123`).
3.  **Prepare Branch**:
    *   Stash current changes: `git stash`
    *   Update main: `git checkout main && git pull origin main`
    *   Create new branch: `git checkout -b ISSUE-<ID>/<short-desc>` (e.g., `ISSUE-123/fix-json-files`)
    *   Apply changes: `git stash pop`. (If conflicts occur, stop and alert the user).
4.  **Commit**:
    *   Delete redundant files: Remove any generated or temporary files that should not be committed.
    *   Stage changes: `git add -A`
    *   Generate a commit message using the Conventional Commits standard (e.g., `feat: ...`, `fix: ...`).
    *   **CRITICAL RULE EXCEPTION**: You are normally forbidden from committing automatically. However, when the user invokes this skill, they are granting explicit permission. Run `git commit -m "<message>"`.
5.  **Create PR**:
    *   Push the branch: `git push -u origin HEAD`
    *   Create the PR: `gh pr create --base main --title "<title>" --body "Resolves #<ID>

<details of changes>"`
6.  **Output**: Print the clickable URL of the newly created PR to the user.
