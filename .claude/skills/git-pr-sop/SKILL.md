---
name: git-pr-sop
description: This skill should be used whenever the user discusses git workflow, branching, or PR mechanics. Activates on keywords like "git branch", "feature branch", "open PR", "draft PR", "commit organization", "merge strategy", "squash merge", "force push", "force-with-lease", "rebase", "hotfix", "review comment", "self-review", "branch protection", "cross-repo paired", "conventional commits", "branch naming". Use to enforce the repo's git/PR SOP and prevent common mistakes (plain --force, direct push to main, missing review etiquette).
---

When the user is doing git or PR work, consult `.trellis/spec/guides/git-pr-sop.md` in the active repo (cwd-aware: the SOP lives in whichever repo's `.trellis/` is in the current working directory). Both `admin` and `platform` carry a paired SOP with mirrored conventions.

## Must-Check Rules

Before executing any git/PR operation, verify against these five rules:

1. **Conventional Commits with scope**: `type(scope): message`. Forbidden: `wip:`, `fixup!`, scope-less `chore: update stuff`. See *Commit Rules* and *Commit Anti-Patterns*.
2. **No `git push --force`** — use `git push --force-with-lease`, and only on unpublished branches. Plain `--force` is in the *Forbidden Git Operations* list.
3. **Draft PR before Ready**: open every PR as `--draft` first, apply *self-review-as-reviewer protocol* using `nit:` / `suggestion:` / `blocking:` taxonomy, then mark Ready only when all `blocking:` threads are resolved.
4. **`--ff-only` for rebased branches**: `git merge <branch> --ff-only`. Never `--no-ff` on a rebased branch — it manufactures a redundant merge node. See *Merge And Cleanup*.
5. **`main` is branch-protected**: PR-first workflow is enforced (`required_pull_request_reviews`, `required_linear_history: true`, `allow_force_pushes: false`). Direct push to `main` will be rejected. Break-glass override requires `[break-glass]:` prefix and admin role.

## Cross-Repo Pairing

When the task touches both `admin` and `platform`, use paired branches with the same name in both repos. Reference each other's commit hashes in PR bodies per `cross-repo-governance.md`. The SOP itself is mirrored — substantive SOP edits ship as a paired PR.

## Where the Full SOP Lives

- Admin: `<admin-repo>/.trellis/spec/guides/git-pr-sop.md`
- Platform: `<platform-repo>/.trellis/spec/guides/git-pr-sop.md`

Read the SOP in the active repo when in doubt. Sections most often consulted: *Branch Naming Convention*, *History Strategy Matrix*, *PR Review Etiquette*, *Hotfix Procedure*, *Branch Protection*.
