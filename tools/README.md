# Project Cybersyn — Companion Tools

Python scripts that automate parts of the Project Cybersyn closed-loop control workflow. All tools are implemented, self-contained, and covered by `smoke_test.py` (55 checks).

## Tools

| Tool | Purpose |
|------|---------|
| `cybersyn_state.py` | Cross-round iteration state manager. Subcommands: `init read update reset query archive apply-audit pause resume migrate lock unlock summary validate`. Enforces safety boundaries (Nmax, consecutive-increase lockout) on write. |
| `complexity_classify.py` | Complexity classifier (L1–L4) from task description and context; `--enforce` emits the control constraints for `init --enforce-from`. |
| `checklist_compare.py` | Acceptance checklist comparator — r(t) requirements vs actual y(t); generates the missing/extra/wrong deviation lists. `code` and `text` modes. |
| `convergence_check.py` | Convergence detector over e(t) history. Extensions: `--energy` (Lyapunov-inspired stability), `--periodic` (limit-cycle detection), `--drift` (environment drift), `--gain`. |
| `audit_trigger.py` | Second-order audit trigger — fires every m rounds or on deviation-pattern anomalies; `--auto-conclude` recommends `maintain / reset-rt / restructure / upgrade-forum`. |
| `handoff_report.py` | Handoff report generator for human-in-the-loop transfer (Nmax exceeded, dead zone, unclassifiable deviation). |
| `diversity_generator.py` | Forum-mode (研讨厅) generator — ≥3 structurally different strategy templates plus a divergence matrix. No LLM calls. |
| `smoke_test.py` | End-to-end smoke test of the whole tool chain (L1 minimal path, L3 full loop, error paths, edge cases). |

## Quick Start

```bash
cd tools

# 1. Classify the task and initialize state
python complexity_classify.py --task "refactor auth module" --files a.py b.py c.py --format json
python cybersyn_state.py init --level L3 --task "refactor auth module"

# 2. Each round: record feedback, check convergence, check audit trigger
python cybersyn_state.py update --stage feedback --data '{"e_missing":[],"e_extra":[],"e_wrong":[],"deviation_type":"A"}'
python convergence_check.py --state cybersyn_state.json --format json
python audit_trigger.py --state cybersyn_state.json --auto-conclude --format json

# 3. On completion or handoff
python cybersyn_state.py summary
python handoff_report.py --state cybersyn_state.json --format json

# Run the test suite
python smoke_test.py
```

The state file location defaults to `./cybersyn_state.json` and can be overridden with the `CYBERSYN_STATE` environment variable.

## Design Constraints

- Python 3 stdlib only (`json`, `pathlib`, `difflib`, `argparse`, `datetime`, `hashlib`)
- Single-file self-contained scripts
- Unified state format: `cybersyn_state.json` (schema v2.0, with automatic migration from v1.0)
- argparse CLI, JSON/text output on stdout, non-zero exit on failure

See `../TOOLING_PLAN_FINAL.md` for the full specification.
