# Project Cybersyn Runtime Tools

These Python standard-library tools implement the evidence-first Project Cybersyn
control loop. Run commands from the skill package root. The state file defaults
to `cybersyn_state.json`; set `CYBERSYN_STATE` to use another path.

## Core tools

| Tool | Purpose |
| --- | --- |
| `cybersyn_state.py` | Create, update, validate, summarize, pause, resume, archive, and hand off iteration state. |
| `complexity_classify.py` | Classify a task from L1 to L4 and emit control constraints. |
| `checklist_compare.py` | Compare requirements with observed output and record deviations. |
| `evidence.py` | Validate requirement evidence, evidence records, and deviation contracts. |
| `finding.py` | Validate Finding records and prevent unsupported findings from blocking delivery. |
| `convergence_check.py` | Check convergence, residuals, drift, periodicity, energy, and gain. |
| `audit_trigger.py` | Trigger second-order audits and recommend a conclusion. |
| `handoff_report.py` | Produce a human handoff when iteration must stop or escalate. |
| `diversity_generator.py` | Produce structurally different strategy templates for forum review. |
| `validation_prompt_assembler.py` | Build read-only validation PromptPackets with risk-based views. |

## Typical loop

```powershell
python tools/complexity_classify.py --task "refactor auth" --files auth.py,api.py --format json
python tools/cybersyn_state.py init --level L3 --task "refactor auth" --requirements "@examples/requirements.json"
python tools/cybersyn_state.py next-round
python tools/cybersyn_state.py update --stage feedback --data "@examples/feedback-converged.json"
python tools/convergence_check.py --state cybersyn_state.json --format json
python tools/audit_trigger.py --state cybersyn_state.json --auto-conclude --format json
python tools/cybersyn_state.py summary
```

`--requirements` accepts a JSON array (or an object containing a
`requirements` array). Each item needs an `id`; its description and test
metadata are preserved in `r_t.requirements`. A feedback payload may include a
`requirement_evidence` array. The state tool validates that it covers every
configured requirement before convergence can allow delivery.

Audits and validation are read-only. A command suggestion is not execution
evidence: test execution requires explicit host authorization and a trusted
command source. A requirement can be delivered only when the evidence ledger
covers every configured requirement and contains no unverified or blocking
residual.
