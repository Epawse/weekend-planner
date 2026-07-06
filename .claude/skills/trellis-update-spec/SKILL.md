---
name: trellis-update-spec
description: "Captures executable contracts and coding conventions into .trellis/spec/ documents. Use when learning something valuable from debugging, implementing, or discussion that should be preserved for future sessions."
---

# Update Code-Spec - Capture Executable Contracts

When you learn something valuable (from debugging, implementing, or discussion), update the relevant code-spec documents. Timing: after completing a task, fixing a bug, or discovering a new pattern.

---

## Code-Spec First Rule

In this project, "spec" for implementation work means **code-spec**:
- Executable contracts (not principle-only text)
- Concrete signatures, payload fields, env keys, and boundary behavior
- Testable validation/error behavior

If the change touches infra or cross-layer contracts, code-spec depth is mandatory.

### Mandatory Triggers

Apply code-spec depth when the change includes any of:
- New/changed command or API signature
- Cross-layer request/response contract change
- Database schema/migration change
- Infra integration (storage, queue, cache, secrets, env wiring)

### Mandatory Output (7 Sections)

For triggered tasks, include all sections below (template at the end of this file):
1. Scope / Trigger
2. Signatures (command/API/DB)
3. Contracts (request/response/env)
4. Validation & Error Matrix
5. Good/Base/Bad Cases
6. Tests Required (with assertion points)
7. Wrong vs Correct (at least one pair)

---

## When to Update Code-Specs

| Trigger | Example | Target Spec |
|---------|---------|-------------|
| **Implemented a feature** | Added a new integration or module | Relevant spec file |
| **Made a design decision** | Chose extensibility pattern over simplicity | Relevant spec + "Design Decisions" section |
| **Fixed a bug** | Found a subtle issue with error handling | Relevant spec (e.g., error-handling docs) |
| **Discovered a pattern** | Found a better way to structure code | Relevant spec file |
| **Hit a gotcha** | Learned that X must be done before Y | Relevant spec + "Common Mistakes" section |
| **Established a convention** | Team agreed on naming pattern | Quality guidelines |
| **New thinking trigger** | "Don't forget to check X before doing Y" | `guides/*.md` (as a checklist item) |

Code-spec updates are NOT just for problems: every feature implementation contains design decisions and contracts that future AI/developers need to execute safely. One-off implementation details that no future session needs can be skipped.

---

## Code-Spec vs Guide - Know the Difference

```
.trellis/spec/
├── <layer>/           # Per-layer coding standards (e.g., backend/, frontend/, api/)
└── guides/            # Thinking checklists (NOT coding specs!)
```

| Type | Location | Purpose | Content Style |
|------|----------|---------|---------------|
| **Code-Spec** | `<layer>/*.md` | Tell AI "how to implement safely" | Signatures, contracts, matrices, cases, test points |
| **Guide** | `guides/*.md` | Help AI "what to think about" | Checklists, questions, pointers to specs |

Decision rule: "this is **how to write** the code" → spec layer directory; "this is **what to consider** before writing" → `guides/`. Guides should be short checklists that point to specs, not duplicate the detailed rules.

---

## Update Process

1. **Identify what you learned**: what, specifically; why it matters (what problem it prevents); which spec file it belongs in.
2. **Read the target code-spec first** — understand existing structure, avoid duplication, find the right section (`cat .trellis/spec/<category>/<file>.md`).
3. **Make the update**. Whatever the entry type (design decision, convention, pattern, anti-pattern, common mistake, gotcha), the shape is the same:
   - State **what** (concrete, with a code example — for don'ts, show wrong vs correct)
   - State **why** (the problem it prevents or the reasoning behind the choice)
   - Show **contracts** where applicable (signatures, payload fields, error behavior)
   - One concept per section; keep it short
4. **Update the category's `index.md`** if you added a new section or the spec status changed.

---

## Mandatory Template for Infra/Cross-Layer Work

```markdown
## Scenario: <name>

### 1. Scope / Trigger
- Trigger: <why this requires code-spec depth>

### 2. Signatures
- Backend command/API/DB signature(s)

### 3. Contracts
- Request fields (name, type, constraints)
- Response fields (name, type, constraints)
- Environment keys (required/optional)

### 4. Validation & Error Matrix
- <condition> -> <error>

### 5. Good/Base/Bad Cases
- Good: ...
- Base: ...
- Bad: ...

### 6. Tests Required
- Unit/Integration/E2E with assertion points

### 7. Wrong vs Correct
#### Wrong
...
#### Correct
...
```

---

## Quality Checklist

- [ ] Specific and actionable, with a code example and the WHY?
- [ ] Executable signatures/contracts included (for triggered tasks: all 7 sections)?
- [ ] In the right file (spec vs guide), no duplication of existing content?

---

## Relationship to Other Commands

`break-loop` (deep bug analysis) often reveals spec updates needed; `update-spec` makes them; `finish-work` reminds you to check whether specs need updates.

> Code-specs are living documents — what AI learns in one session persists to future sessions, and mistakes become documented guardrails.
