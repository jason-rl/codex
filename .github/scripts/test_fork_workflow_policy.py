#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / "workflows"
MANUAL_TRIGGERS = {"workflow_call", "workflow_dispatch"}


def workflow_triggers(path: Path) -> set[str]:
    lines = path.read_text().splitlines()
    try:
        on_line = next(index for index, line in enumerate(lines) if line == "on:")
    except StopIteration as error:
        raise AssertionError(f"{path.name} does not contain a top-level on mapping") from error

    triggers = set()
    for line in lines[on_line + 1 :]:
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([a-z_]+):", line)
        if match:
            triggers.add(match.group(1))
    return triggers


def workflow_on_mapping(path: Path) -> str:
    lines = path.read_text().splitlines()
    on_line = lines.index("on:")
    end_line = next(
        (
            index
            for index, line in enumerate(lines[on_line + 1 :], start=on_line + 1)
            if line and not line.startswith(" ")
        ),
        len(lines),
    )
    return "\n".join(lines[on_line:end_line])


class ForkWorkflowPolicyTest(unittest.TestCase):
    def test_only_rust_release_runs_automatically(self) -> None:
        violations = []
        for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
            triggers = workflow_triggers(path)
            automatic_triggers = triggers - MANUAL_TRIGGERS
            if path.name == "rust-release.yml":
                if triggers != {"push"}:
                    violations.append(
                        f"{path.name}: expected only push, found {sorted(triggers)}"
                    )
            elif automatic_triggers:
                violations.append(
                    f"{path.name}: automatic triggers {sorted(automatic_triggers)}"
                )

        self.assertEqual([], violations)

    def test_rust_release_only_runs_for_main(self) -> None:
        on_block = workflow_on_mapping(WORKFLOWS_DIR / "rust-release.yml")
        self.assertIn("  push:\n    branches: [main]", on_block)
        self.assertNotIn("    tags:", on_block)


if __name__ == "__main__":
    unittest.main()
