# Forward-evaluation observations

`contract-harness.jsonl` contains the first 150 static contract observations (30 cases × 5 variants).
They verify routing and safety invariants only; they are not claims about real Agent task completion,
user interruptions, or production regression rates. Those fields remain unobserved until fresh Agent
runs provide raw observations.

Variants:

- `no-skill`
- `v1.2-evidence-only`
- `v1.3-single-auditor`
- `v1.3-multi-angle`
- `v1.4`

Replace or supplement this file with fresh observations from isolated runs before making a release
decision. The evaluator preserves missing metrics instead of treating them as zero.
