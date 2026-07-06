---
name: trellis-grill-me
description: "Grill the PRD before task.py start: one bounded adversarial pass that attacks every requirement with four hammers (deletion, boundary, testability, conflict), verifies factual premises against the repo first, and rewrites the PRD with confirmed findings. Use when the user accepts a grill-me recommendation, explicitly asks to 逼问/压测需求, or sets --grill-me enabled in the Development Strategy."
---

# Trellis Grill-Me

One bounded adversarial pass over `prd.md`. Not a second brainstorm: brainstorm builds the requirements up; grill-me tries to knock them down. Run it after the PRD converges and before `task.py start`.

## Contract

- Exactly one pass unless the user explicitly asks for another round.
- Every finding is one sentence and ships with a recommended fix — the user corrects a proposal, never faces a blank question.
- Attack the artifact, not the user: rewrite first, ask only when a finding needs a product decision.
- Explicit bypass: if the user has already made the call ("就这么定"), skip the affected hammer and record the ruling.
- Follow the user's language for all output.

## Step 0: Verify Premises Against the Repo

Before swinging any hammer, fact-check the PRD's claims about current behavior against the codebase (and existing specs/tests). A wrong premise makes every downstream finding noise. Anything the repo can answer becomes a verified statement, not a question to the user.

## The Four Hammers

Apply each to every requirement and acceptance criterion in `prd.md`:

1. **Deletion** — If this line were dropped, what breaks, for whom, when? No concrete answer → delete it or mark it `nice-to-have`.
2. **Boundary** — What happens at zero / max / concurrent / failure? Check the repo for existing boundary handling first; if the PRD is silent and the answer matters, add the missing constraint.
3. **Testability** — Write the exact command or step that would verify this criterion today. Cannot write one → tag `UNVERIFIABLE` and rewrite the criterion until you can.
4. **Conflict** — Scan pairs of requirements for hidden tension (fast vs simple, compatible vs clean, scope vs deadline). Surface each tension as an explicit either/or **with your recommended side**.

After all four: one cross-check — do this round's own findings contradict each other (e.g. a conflict ruling invalidating a boundary you just added)? Reconcile before reporting.

## Finding Bar

Promote something to a formal finding only when it clears all three: (a) hard to fix after implementation starts, (b) likely to be missed if unstated, (c) a real decision with more than one defensible answer. Everything below the bar is silently fixed in the rewrite or dropped — Grill Findings must stay short enough to be read.

## Output

1. Rewrite `prd.md` in place: deletions, downgrades, added constraints, testable criteria.
2. Append a `## Grill Findings` section: what was deleted/downgraded, conflicts surfaced (and the user's rulings), risks still open.
3. Record the pass in the Development Strategy:

```bash
python3 ./.trellis/scripts/task.py set-strategy "$TASK_DIR" --grill-me enabled
```

4. Report back in ≤5 bullets and ask for one explicit confirmation of the revised PRD. **The rewrite is a proposal until the user confirms it** — do not treat the PRD as settled, and do not proceed toward `task.py start`, on silence.

## Boundaries

- Do not touch `design.md` / `implement.md` — grill-me is requirements-only.
- Do not block `task.py start`: this is an optional enhancer, and its absence is never a gate failure.
- If the user declines findings, keep their ruling and move on — no re-litigation.
