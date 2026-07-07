#!/usr/bin/env python3
"""Unit tests for GitHub Action helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "lib"))

import action as permissions_action  # noqa: E402
from permissions import GateError  # noqa: E402


class ActionHelperTest(unittest.TestCase):
    def test_evaluate_from_paths_returns_verdict_and_event_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            (workspace / "event.json").write_text(
                json.dumps({"issue": {"number": 7, "user": {"login": "stranger"}}}),
                encoding="utf-8",
            )

            verdict, event = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.actor, "user:stranger")
        self.assertEqual(event["issue"]["number"], 7)

    def test_validate_on_deny_rejects_unknown_values(self) -> None:
        with self.assertRaises(GateError) as raised:
            permissions_action.validate_on_deny("delete")

        self.assertEqual(raised.exception.field, "on-deny")

    def test_outputs_for_verdict_formats_action_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            (workspace / "event.json").write_text(
                json.dumps({"issue": {"number": 7, "user": {"login": "rikonor"}}}),
                encoding="utf-8",
            )
            verdict, _ = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

        outputs = permissions_action.outputs_for_verdict(verdict)

        self.assertEqual(outputs["allowed"], "true")
        self.assertEqual(outputs["actor"], "user:rikonor")
        self.assertEqual(outputs["gate"], "issue")

    def test_close_denied_closes_denied_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            event = {"issue": {"number": 7, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, str]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, str]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                permissions_action.close_denied(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                )

        self.assertEqual(
            calls,
            [
                (
                    "PATCH",
                    "https://api.github.test/repos/KnickKnackLabs/permissions/issues/7",
                    "token",
                    {"state": "closed"},
                )
            ],
        )

    def test_close_denied_closes_denied_pull_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.pull_request]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            event = {"pull_request": {"number": 3, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="pull-request",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, str]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, str]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                permissions_action.close_denied(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                )

        self.assertEqual(
            calls[0][1],
            "https://api.github.test/repos/KnickKnackLabs/permissions/pulls/3",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
