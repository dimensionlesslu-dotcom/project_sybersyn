#!/usr/bin/env python3
"""Minimal Skill frontmatter validator used by CI and release checks."""

import re
import sys
from pathlib import Path

import yaml


ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata"}


def validate_skill(skill_path):
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"
    content = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return False, f"Invalid YAML in frontmatter: {exc}"
    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary"
    unexpected = set(frontmatter) - ALLOWED_PROPERTIES
    if unexpected:
        return False, f"Unexpected key(s): {', '.join(sorted(unexpected))}"
    if not isinstance(frontmatter.get("name"), str) or not frontmatter["name"].strip():
        return False, "Missing or invalid name"
    if not re.match(r"^[a-z0-9-]+$", frontmatter["name"].strip()):
        return False, "Name must be hyphen-case"
    if not isinstance(frontmatter.get("description"), str):
        return False, "Description must be a string"
    if len(frontmatter["description"].strip()) > 1024:
        return False, "Description is too long"
    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
