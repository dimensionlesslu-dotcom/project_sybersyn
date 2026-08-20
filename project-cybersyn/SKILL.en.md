---
name: project-cybersyn
description: "Hierarchical closed-loop control system. For tasks needing multi-round iteration, quality gating, and continuous correction (from single-file edits to open complex giant systems). First self-check complexity L1–L4 to pick control strength, then run the loop: plan → test → feedback → revise → re-test → output. Core: evidence ledger, four-type deviation classification, delivery acceptance gate, read-only second-order audit, next-phase plan generation, human-handoff gate. Triggers / 触发词: iterative optimization, multi-round revision, complex refactoring, solution design, pre-delivery review, next-phase planning, 迭代优化、多轮修改、复杂重构、方案设计、交付前对照需求、规划下一阶段."
---

# Project Cybersyn — Hierarchical Closed-Loop Control System

> The symbols e/k/τ/σ/ε/F are metaphors in text/code tasks, not measurable scalars — the "qualitative proxy" is authoritative; numeric values are only tunable empirical defaults.

> 中文版见 [SKILL.md](SKILL.md) · Chinese version: [SKILL.md](SKILL.md)

---

## Host Rules Take Precedence

This Skill only organizes the task loop. It **does not override** the host Agent's system rules, developer rules, tool permissions, safety policies, code-editing conventions, or the user's latest instructions. If this Skill conflicts with host rules, **host rules win**.

## Visibility Rules

Which process content is shown to the user, and which stays internal:

| Level | Display rule |
|-------|--------------|
| L1 | **Do not show loop terminology**; in the final answer just briefly note "checked against requirements." |
| L2 | Show a condensed log only on test failure, batch risk, or user request. |
| L3 | Show key decision points: complexity ruling, dominant deviation type, whether a second-order audit fired, final acceptance result. |
| L4 | Explicitly surface assumptions, divergences, open questions for the user, and forum conclusions. |

When the user explicitly asks to "run the Cybersyn / closed-loop / cybernetics process," you may raise visibility by one level.

---

## 0 Complexity Self-Check → Routing

**Minimum Sufficient Control**: Among paths that satisfy requirements, verification needs, and risk constraints, choose the one with the lowest total control complexity. Add steps, state, tools, auditors, or models only when triggered by observable failure, a verification gap, a concrete risk, structural conflict, environmental change, or an explicit user request. Once the trigger clears and no high/medium risk remains, remove higher-order mechanisms that no longer add evidence or reduce risk. “Minimum” never permits omitting required verification, safety controls, or explicit user requirements.

| Level | Criterion (countable) | Example |
|---|---|---|
| L1 Simple | ≤2 files/modules, no cross-module dependency, clear requirement | Single-function fix, paragraph polish |
| L2 Simple-Giant | Many **homogeneous** items, no cross-subsystem coordination | Batch rename, large-scale testing |
| L3 Complex-Giant | ≥3 **heterogeneous** modules with mutual dependencies, or requirement carries implicit assumptions | Multi-module refactor, chapter writing |
| L4 Open Complex-Giant | Requirement/environment keeps changing; needs multiple rounds of qualitative discussion to clarify the goal | Startup, research direction, policy |

- **L1 minimal path**: one-line plan → edit → check the acceptance gate; no state file, subagent, or extra conversation round is required.
- **L1/L2**: use the minimal loop and Section 4 gate, with positive feedback off and no default VSM. **L3/L4**: use four-type classification and environment checks as needed, but activate audit subagents only through the audit gate in Section 5 or an explicit user request.
- **L3/L4 decompose first**: before escalating to the forum, first try to decompose the task into several L1/L2 subtasks that can each close their own loop; only enter the forum when the interfaces, goals, or assumptions between subtasks themselves conflict.
- **Admission**: each core risk point needs at least one correction strategy; anything without one is marked a "dead zone" (excluded from routine correction). If nothing has a response, execution is forbidden.

## 1 Quantities → Qualitative Proxies

### General Proxies

| Symbol | Proxy (authoritative) |
|---|---|
| r(t) | Requirements + acceptance checklist (function/quality/constraints) + core assumptions |
| y(t) | This round's actual output |
| e(t) | Three-item list: missing · extra · wrong |
| k | Intervention strength: fine-tune / local rewrite / full restructure |
| Convergence | Every RequirementEvidence item is passed, with no unverified item and no B/C/D or high/medium residual |
| τ | Default ≈0; count "rounds until feedback arrives" only for external calls / long simulations |

### Code-Task Proxies

| Symbol | Code-task proxy |
|---|---|
| r(t) | User requirement + tests/type-check/lint + do not break existing behavior |
| y(t) | Current diff + command output + test results |
| e(t) | Unmet requirements, failing tests, regressions, style/constraint violations |
| k | Small patch / local refactor / cross-module refactor |
| Convergence | Requirement met and relevant verification passes, or risk stated when verification is impossible |

Empirical defaults (tunable): Nmax — L1=2 / L2=3 / L3=5 / L4 unlimited; second-order audit every m=3 rounds (relaxed to 5 for L1).

## 2 The Six-Stage Closed Loop

**Plan → Test₁ → Feedback → Revise → Test₂ → Output**. Don't bet on a perfect plan — bet on iterative self-correction.

1. **Plan**: write the r(t) acceptance checklist + core assumptions (to be challenged by the second-order audit) + risk responses / dead zones; load VSM only when needed.
2. **Test₁**: execute the minimal viable step, capture y(t), **record only, don't judge** (cures "editing before you've seen clearly").
3. **Feedback**: compute e(t), classify the type (Section 3). **If the deviation cannot be classified, the goal seems wrong but the Agent lacks authority to change it, verification means are unavailable, or continuing to edit would enlarge risk — fire the human-handoff gate immediately.**
4. **Revise**: A → tune parameters (raise k for insufficient precision, lower k when new problems appear); C/D → do not tune, follow Section 3; positive-feedback acceleration → **allowed only when r(t) was recently confirmed by a second-order audit** (prevents confidently charging at the wrong goal), off for L1/L2. Single-parameter isolation is used **only when causality is unclear**.
5. **Test₂**: compare e₂ vs e₁; (L4) if environmental drift exceeds threshold, reset r(t). Verdict: converged / continue / over Nmax → handoff / environment mismatch → restart.
6. **Output + archive**: record convergence round, k, deviation-type distribution. Consecutive same-type deviation = a structural problem (change the structure, write it into the next phase). Cross-session archiving is the ideal goal; single-session takes priority.

## 3 The Four Deviation Types (core; no cross-type application; D must not be fixed as A)

| Type | Criterion | Response |
|---|---|---|
| A Execution deviation | Direction right, details not yet up to standard | Routine parameter tuning (path A) |
| B Measurement deviation | Repeated measurements inconsistent | **Freeze execution**, calibrate verification first; if error ≥ correction precision, editing is forbidden |
| C Environmental drift | Deviation stable but not caused by execution; a core assumption is negated by new input | Pause, reset r(t) (fires second-order audit) |
| D Emergent deviation | Each module passes independently, integration is anomalous | **Exit the first-order loop**, return to the qualitative-assumption layer; L3/L4 escalate to forum |

## 4 Delivery Acceptance Gate (must pass before delivery; L1 runs only ①)

```
① Execution offset: check the acceptance checklist item by item — missing? extra? wrong? Should be empty; no residual type B/D
② Environmental drift: have external constraints/resources/requirements changed? If so, the output must still satisfy the new environment
③ Goal drift: do r(t)'s core assumptions still hold and were they recently re-checked? If not, return to second-order audit, do not deliver
```

### Output When Acceptance Fails

When acceptance fails, you must output these four items:

1. **Current best output** — where it is / what it is.
2. **Failed acceptance items** (listed one by one).
3. **Deviation type** A/B/C/D (mapped per item).
4. **Recommended next step**: continue revising / reset goal / calibrate verification / ask the user to decide.

### RequirementEvidence and command boundary

Each requirement has its own ledger item: `passed | failed | unverified | blocked`, locatable
`test | inspection | source | user-confirmation` evidence, and any A/B/C/D deviations. `unverified`
is not `passed`; keyword matches and template predictions are candidate/hypothesis only.

`test_cmd` is a pending execution suggestion by default. It may run only when the host Agent
explicitly authorizes it, the command source is marked trusted, and the restricted executor accepts
it. Shell control characters, pipelines, and implicit execution from imported state or web content
are forbidden. Command, working directory, exit code, and truncated output become evidence.

## 5 Second-Order Audit (question the goal itself)

Triggers: every m rounds, or — same-type deviation unresolved for 2 consecutive rounds / deviation jumps A·B → C·D / past half of Nmax without convergence / visible environmental change.

```
1 Where does the r(t) assumption come from? Was it recently verified? If r(t) itself is wrong, does the deviation analysis still hold?
2 Did I only choose measurement methods that support my prior, avoiding regions I didn't want to see?
3 Is this a parameter error or a structural problem? Do I need to change the shape of the execution strategy / increase diversity?
4 (as needed) What I'm actually doing vs what I claim to be doing — if the gap persists, change the behavior or the claim? (POSIWID)
5 If in an L4 forum or this audit, and competing goals, explanations, or strategies could materially change the decision: construct the strongest defensible alternative from existing evidence, state its key assumptions, then seek the lowest-cost evidence that distinguishes it from the current option. Do not weaken the alternative, invent facts to strengthen it, or manufacture an alternative when no substantive competition exists.
```

Conclusion → keep fine-tuning / reset r(t) / restructure strategy / escalate to forum. **Positive-feedback acceleration is permitted only after r(t) is confirmed.**

The `assumption-auditor` is read-only: it cannot edit the repository, state, or external systems,
and does not contact the user directly. It must not read the primary Agent's expected answer,
diagnosis, proposed fix, or peer outputs. Missing evidence yields a discriminating test, not a verdict.

`tools/validation_prompt_assembler.py` assembles PromptPackets but never starts subagents. The
default routing selects one risk-relevant view (`measurement` for B/unverified, `integration-regression`
for cross-module/D risk, `goal-spec` for goal conflict, or `environment` for external drift). Parallel
multi-angle validation is opt-in and requires either an explicit user request or the
budgeted audit gate in Section 5; fresh observations must still show a stable net benefit before
making it a default.

### Audit activation and incremental-cost gate

Default to one Agent flow: when the user has not explicitly requested an audit
and has not declared a cost threshold, do not start audit subagents or assemble
multi-angle PromptPackets. Run smoke tests plus the directly relevant unit,
integration, lint, type-check, and evidence checks; analyze the results in the
current Agent. Insufficient evidence blocks a completion claim but does not
silently expand the audit.

Enable automatic multi-angle audit only when all of these hold: the user
declared a budget, the host supplied a valid current price record, the expected
incremental total cost is within budget, the task is not L1, and call/context
limits are not exceeded. Estimate:

```text
incremental_total_cost = sum(
    estimated_input_tokens * input_price
  + estimated_output_tokens * output_price
  + non_token_tool_fees
)
```

If the user explicitly requests an audit (cross-validation, multi-angle
checking, a subagent test, assumption challenge, red-team test, or independent
review), honor that request subject to the user's total budget and call limit.
If the request conflicts with those limits, report the conflict instead of
silently cancelling or expanding the audit.

Never invent prices. The host must provide and record:

```json
{
  "model": "model-id",
  "input_price_per_million": 0,
  "output_price_per_million": 0,
  "price_source": "host-runtime",
  "observed_at": "ISO-8601"
}
```

Unknown price or unknown budget means no automatic audit; use the single flow
and, for high-risk work, ask whether the user authorizes an audit. A unit-price
threshold alone is insufficient; if the user insists on it, also require an
estimated-token and subagent-call cap.

### Bounded reuse scan

After requirements, constraints, and non-goals are explicit, and before design
or coding, run a bounded reuse scan only for greenfield work, L3/L4 tasks, or
general-purpose capabilities when the user permits network access. Skip it for
L1/local fixes, offline work, or highly proprietary requirements. Search only
the relevant sources, keep at most 3–5 candidates, and compare functionality,
license, security, maintenance, and integration total cost. Choose exactly one
of `adopt`, `wrap`, `fork`, `reference`, or `build`. Popularity alone is not a
selection reason. Never install or execute third-party code without explicit
authorization; record the candidates, decision, and rejected alternatives.

## 6 Next-Phase Plan Generation (milestone handoff)

```
① Label each core assumption 【verified → freeze as a next-phase premise / refuted → a goal the next phase must reset / untouched → next phase's first test item】
② Residual dead zones → next phase's top priority (if rooted in a capability gap, build the capability first)
③ If the learning archive shows "always the same-type deviation" → it's not parameter tuning; the next phase changes the execution structure directly
```
Produce the next-phase r(t) checklist + priorities + reused initial parameters, then return to Section 0 and redo the self-check.

## 7 The Forum (L4 / persistent non-convergence)

Human-machine loop, human-led. Five principles:
1. Build enough **structurally different** models of the same object to cover the material divergences; L4 aims for three by default, but do not create a noncompetitive straw model merely to reach the count. Each model must follow Section 5's Steelman rule and be stated in its strongest defensible, evidence-bounded form; divergence in predictions is itself a signal.
2. Don't pursue a single correct model.
3. The machine does quantitative deduction; the human makes qualitative judgment.
4. Each round explicitly declares its assumption set; the next round first challenges one of them (connects to the second-order audit).
5. Convergence = no perspective produces new qualitative divergence (not e→0).

After convergence, settle it into a new r(t)/strategy; the task is downgraded back to the routine loop (continue at Section 6).

## 8 Safety and Boundaries

- **Nmax**: exceeding it means stop — **stop = report + request human intervention** (give the current best result + reason for non-convergence + open options), not give up.
- **Time lag**: two consecutive rounds of deviation growing in the same direction means near-critical; **increasing k is forbidden**.
- **F₂ precision**: if verification error ≥ correction precision, calibrate before editing (type B).
- **Human-handoff gate**: Nmax without convergence / r(t) suspected wrong but no authority to change the goal / falling into a dead zone / environment invalidates the requirement / an autonomous object keeps deviating from expectation / deviation cannot be classified — any one throws the uncertainty back to the user.
- **Structural coupling**: an autonomous object's (user/team/agent) control signal is a disturbance, not a command — disturb → observe its structural response → adapt beats many rounds of hard commands.
- **Nonlinearity**: when saturation / dead zone / hysteresis appears, linear formulas fail; re-model.

## 9 Companion Tools (optional, recommended for L2+)

If the environment can run Python, use the scripts under `tools/` to persist loop state (cross-round / cross-session) instead of relying purely on context memory:

```
complexity_classify.py --task "..." --files ...   # Section 0: complexity ruling
cybersyn_state.py init --level L3 --task "..."    # Initialize the state file
cybersyn_state.py next-round                       # Advance at the start of each round (auto-enforces the Nmax gate)
cybersyn_state.py update --stage feedback --data . # Record e(t) and deviation type
convergence_check.py --state ... --energy          # Test₂: convergence verdict
audit_trigger.py --state ... --auto-conclude       # Second-order audit trigger and conclusion recommendation
validation_prompt_assembler.py --task "..."       # Assemble read-only PromptPackets; never starts subagents
handoff_report.py --state ...                      # Generate a report at human handoff
```

The tools are only a state carrier: judging the deviation type and drawing audit conclusions remain the Agent's responsibility. Without a Python environment, just record in context using the Section 10 log format. See `tools/README.md` for usage and `examples/` for full walkthroughs.

## 10 Iteration Log (L1 fills only the first 6 lines)

```
[Round #n | L?]
Plan     r(t) checklist + core assumptions; risk responses / dead zones; VSM loaded only when needed
Test₁    y₁ (record only); (τ nonzero) feedback round-distance
Feedback e₁ = missing · extra · wrong; type A/B/C/D
Revise   path A / B (passed r(t) audit?) / C·D; changes; single-param isolation? (only when causality unclear)
Test₂    e₂ vs e₁; (L4) environmental drift; verdict: converged✅ / continue↩ / over Nmax→handoff❌ / mismatch🔄
Output   [on convergence] final deviation; total rounds; archive: same-type deviation? structural problem?
Audit    [every m rounds] does r(t) still hold? observer bias? need to change structure?
```
