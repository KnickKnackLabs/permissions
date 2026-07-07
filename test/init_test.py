#!/usr/bin/env python3
"""Unit tests for permissions init planning and rendering."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "lib"))

from init.cli import files_requiring_overwrite, write_statuses  # noqa: E402
from init.models import InitOptions, options_from_env, validate_options  # noqa: E402
from init.render import apply_plan, build_plan  # noqa: E402
from permissions import GateError  # noqa: E402


class InitOptionsTest(unittest.TestCase):
    def test_options_from_env_parses_variadic_usage_values(self) -> None:
        options = options_from_env(
            {
                "usage_gate": "issue 'pull-request'",
                "usage_allow": "user:rikonor team:KnickKnackLabs/agents",
                "usage_on_deny": "close",
                "usage_write": "true",
            }
        )

        self.assertEqual(options.gates, ("issue", "pull-request"))
        self.assertEqual(options.allow, ("user:rikonor", "team:KnickKnackLabs/agents"))
        self.assertTrue(options.write)

    def test_validate_options_rejects_unsupported_principals(self) -> None:
        with self.assertRaises(GateError) as raised:
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("org:KnickKnackLabs",),
                    on_deny="close",
                )
            )

        self.assertIn("unsupported principal", raised.exception.message)

    def test_validate_options_rejects_principal_injection(self) -> None:
        with self.assertRaises(GateError) as raised:
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=('user:rikonor"\nmalicious = true',),
                    on_deny="close",
                )
            )

        self.assertIn("unsupported principal", raised.exception.message)

    def test_validate_options_rejects_action_ref_injection(self) -> None:
        with self.assertRaises(GateError) as raised:
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("user:rikonor",),
                    on_deny="fail",
                    action_ref="v0.5.0\n        env:\n          PWN: x",
                )
            )

        self.assertIn("action-ref", raised.exception.message)

    def test_validate_options_rejects_invalid_membership_secret_names(self) -> None:
        with self.assertRaises(GateError) as raised:
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("team:KnickKnackLabs/agents",),
                    on_deny="fail",
                    membership_token_secret="permissions-token",
                )
            )

        self.assertIn("membership-token-secret", raised.exception.message)


class InitRenderTest(unittest.TestCase):
    def test_build_plan_renders_team_workflows_with_membership_secret(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue", "pull-request"),
                    allow=("team:KnickKnackLabs/agents",),
                    on_deny="close",
                    membership_token_secret="PERMISSIONS_MEMBERSHIP_TOKEN",
                )
            )
        )

        files = {str(file.path): file.content for file in plan.files}

        self.assertIn('"team:KnickKnackLabs/agents"', files["permissions.toml"])
        self.assertIn(
            "membership-token: ${{ secrets.PERMISSIONS_MEMBERSHIP_TOKEN }}",
            files[".github/workflows/permissions-issue-gate.yml"],
        )
        self.assertIn(
            "pull_request_target",
            files[".github/workflows/permissions-pull-request-gate.yml"],
        )
        self.assertIn(
            "pull-requests: write",
            files[".github/workflows/permissions-pull-request-gate.yml"],
        )

    def test_team_plan_warns_when_membership_secret_is_missing(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("team:KnickKnackLabs/agents",),
                    on_deny="fail",
                )
            )
        )

        self.assertTrue(plan.warnings)
        self.assertTrue(any("read:org" in item for item in plan.guidance))

    def test_apply_plan_refuses_team_workflows_without_secret_by_default(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("team:KnickKnackLabs/agents",),
                    on_deny="fail",
                    write=True,
                )
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(GateError) as raised:
                apply_plan(plan, Path(tmpdir))

        self.assertIn("--membership-token-secret", raised.exception.message)

    def test_files_requiring_overwrite_returns_changed_existing_files(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("user:rikonor",),
                    on_deny="fail",
                )
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "permissions.toml").write_text("old\n", encoding="utf-8")

            self.assertEqual(
                files_requiring_overwrite(plan, root), (Path("permissions.toml"),)
            )

    def test_write_statuses_reports_created_and_updated_before_write(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("user:rikonor",),
                    on_deny="fail",
                )
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "permissions.toml").write_text("old\n", encoding="utf-8")

            self.assertEqual(
                write_statuses(plan, root),
                {
                    Path("permissions.toml"): "updated",
                    Path(".github/workflows/permissions-issue-gate.yml"): "created",
                },
            )

    def test_apply_plan_writes_files_when_inputs_are_complete(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("user:rikonor",),
                    on_deny="fail",
                    write=True,
                )
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            apply_plan(plan, root)

            self.assertTrue((root / "permissions.toml").exists())
            self.assertTrue(
                (root / ".github/workflows/permissions-issue-gate.yml").exists()
            )

    def test_apply_plan_preflights_overwrites_before_writing_any_file(self) -> None:
        plan = build_plan(
            validate_options(
                InitOptions(
                    gates=("issue",),
                    allow=("user:rikonor",),
                    on_deny="fail",
                    write=True,
                )
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workflow = root / ".github/workflows/permissions-issue-gate.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("old\n", encoding="utf-8")

            with self.assertRaises(GateError) as raised:
                apply_plan(plan, root)

            self.assertIn("refusing to overwrite", raised.exception.message)
            self.assertFalse((root / "permissions.toml").exists())
            self.assertEqual(workflow.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
