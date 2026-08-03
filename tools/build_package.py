#!/usr/bin/env python3
"""Build the minimal installable Project Cybersyn skill package."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "project-cybersyn"
FILES = [
    "SKILL.md", "SKILL.en.md", "LICENSE",
    "agents/openai.yaml", "agents/assumption-auditor.md",
    "references/subagent-validation.md",
    "tools/README.md",
    "tools/audit_trigger.py", "tools/checklist_compare.py",
    "tools/complexity_classify.py", "tools/convergence_check.py",
    "tools/cybersyn_state.py", "tools/diversity_generator.py",
    "tools/evidence.py", "tools/finding.py", "tools/handoff_report.py",
    "tools/validation_prompt_assembler.py",
    "examples/L1-simple-task.md", "examples/L3-complex-task.md",
    "examples/feedback.json",
    "examples/requirements.json", "examples/feedback-converged.json",
]


def build(destination=DESTINATION):
    # The output directory is a generated artifact. Rebuilding it from the
    # manifest prevents stale files from surviving a source/package change.
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for relative in FILES:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


if __name__ == "__main__":
    print(build())
