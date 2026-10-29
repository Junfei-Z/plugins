# Research debate protocol

Use the lightest phase sequence that fits the research stage. Do not force all phases onto a narrow question.

## Phase 0 — Scope

Record the observed phenomenon, target population or workload, claimed contribution, constraints, and what the user has not decided yet. Separate evidence from intuition.

## Phase 1 — Problem validation

Ask:

- Does the failure exist in measured settings?
- Is it widespread or workload-specific?
- Which cheap guard, heuristic, cache, or accounting fix might remove it?
- What observation would kill the project before implementation?

Prefer a characterization or discriminating experiment over architecture work.

## Phase 2 — Literature and overlap

Build a comparison table covering problem, state, action, objective, evaluation, and missing capability. Mark each source:

- **V — verified:** primary paper or official artifact inspected;
- **P — partial:** metadata or indirect evidence only;
- **U — unverified:** lead requiring follow-up.

Use “not identified in our search,” never “no prior work,” unless the search is systematic and documented.

## Phase 3 — Mechanism

Move below the surface symptom. Look for a hidden coupling, wrong assumption, missing abstraction, measurement gap, or inherent tension. Try to complete:

> We found that **M** causes **P** under **C**; existing methods fail because they assume **A**.

If the statement is merely “nobody combined X and Y,” keep digging.

## Phase 4 — Competing formulations

Compare the preferred approach against simple rules, decomposed controllers, classical optimization, and relevant learned methods. Match information, tuning budget, and action space. Do not give the preferred method privileged signals.

Pre-register predictions that could make the preferred method lose.

## Phase 5 — Synthesis

Rank at most three candidate questions. For each, report:

- mechanism;
- novelty risk;
- nearest threats;
- minimum viable experiment;
- resource estimate;
- kill criterion.

End with a human decision, not another automatic round.

## Suggested message labels

```text
[PHASE 1/5][REVIEWER][TO:proposer]
[PHASE 1/5][PROPOSER][TO:reviewer]
[HUMAN_DECISION_REQUIRED]
[AUTO_PAUSED]
```

Keep each message single-purpose. Large datasets, code, and full papers should be referenced by path or link rather than pasted into the transcript.
