"""Render permissions init files and plans."""

from __future__ import annotations

from pathlib import Path

from permissions import GateError

from .models import (
    DEFAULT_MEMBERSHIP_SECRET,
    InitOptions,
    InitPlan,
    PlannedFile,
    has_team_principals,
)


def build_plan(options: InitOptions) -> InitPlan:
    """Build a concrete init plan."""
    warnings: list[str] = []
    guidance: list[str] = []
    if has_team_principals(options.allow):
        secret = options.membership_token_secret or DEFAULT_MEMBERSHIP_SECRET
        guidance.extend(membership_token_guidance(secret))
        if not options.membership_token_secret:
            warnings.append(
                "team principals need a membership-readable token; default workflow "
                "tokens usually cannot read closed/private team membership"
            )

    files: list[PlannedFile] = [
        PlannedFile(Path("permissions.toml"), render_permissions_toml(options)),
    ]
    if "issue" in options.gates:
        files.append(
            PlannedFile(
                Path(".github/workflows/permissions-issue-gate.yml"),
                render_issue_workflow(options),
            )
        )
    if "pull-request" in options.gates:
        files.append(
            PlannedFile(
                Path(".github/workflows/permissions-pull-request-gate.yml"),
                render_pull_request_workflow(options),
            )
        )
    return InitPlan(
        options=options,
        files=tuple(files),
        warnings=tuple(warnings),
        guidance=tuple(guidance),
    )


def membership_token_guidance(secret_name: str) -> tuple[str, ...]:
    """Return guidance for creating and storing a membership token."""
    url = (
        "https://github.com/settings/tokens/new?"
        "description=permissions-membership-token&scopes=read:org"
    )
    return (
        "Team principals require a token that can read organization team membership.",
        f"Create a token with read:org: {url}",
        f"Store it for this repo: gh secret set {secret_name}",
    )


def render_permissions_toml(options: InitOptions) -> str:
    """Render permissions.toml."""
    sections: list[str] = []
    for gate in options.gates:
        section = "pull_request" if gate == "pull-request" else "issue"
        noun = "pull requests" if gate == "pull-request" else "issues"
        lines = [
            f"[gate.{section}]",
            'default = "deny"',
            "allow = [",
            *[f'  "{principal}",' for principal in options.allow],
            "]",
            f'message = "This repo only accepts {noun} from configured principals."',
        ]
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def render_issue_workflow(options: InitOptions) -> str:
    """Render the issue gate workflow."""
    return (
        "name: Permissions Issue Gate\n\n"
        "on:\n"
        "  issues:\n"
        "    types: [opened, reopened]\n\n"
        "permissions:\n"
        "  contents: read\n"
        f"{issue_write_permission(options)}"
        "\n"
        "jobs:\n"
        "  issue-gate:\n"
        "    runs-on: ubuntu-latest\n\n"
        "    steps:\n"
        "      - name: Checkout default branch policy\n"
        "        uses: actions/checkout@v6\n"
        "        with:\n"
        "          ref: ${{ github.event.repository.default_branch }}\n\n"
        "      - name: Evaluate issue author\n"
        f"        uses: KnickKnackLabs/permissions@{options.action_ref}\n"
        "        with:\n"
        "          gate: issue\n"
        f"          on-deny: {options.on_deny}\n"
        f"{membership_token_line(options)}"
    )


def render_pull_request_workflow(options: InitOptions) -> str:
    """Render the pull request gate workflow."""
    return (
        "name: Permissions Pull Request Gate\n\n"
        "on:\n"
        "  pull_request_target:\n"
        "    types: [opened, synchronize, reopened, ready_for_review]\n\n"
        "permissions:\n"
        "  contents: read\n"
        f"{pull_request_write_permissions(options)}"
        "\n"
        "jobs:\n"
        "  pull-request-gate:\n"
        "    runs-on: ubuntu-latest\n\n"
        "    steps:\n"
        "      - name: Checkout base branch policy\n"
        "        uses: actions/checkout@v6\n"
        "        with:\n"
        "          ref: ${{ github.event.pull_request.base.sha }}\n\n"
        "      - name: Evaluate pull request author\n"
        f"        uses: KnickKnackLabs/permissions@{options.action_ref}\n"
        "        with:\n"
        "          gate: pull-request\n"
        f"          on-deny: {options.on_deny}\n"
        f"{membership_token_line(options)}"
    )


def issue_write_permission(options: InitOptions) -> str:
    """Return issue workflow write permissions when needed."""
    if options.on_deny == "close":
        return "  issues: write\n"
    return ""


def pull_request_write_permissions(options: InitOptions) -> str:
    """Return PR workflow write permissions when needed."""
    if options.on_deny == "close":
        return "  issues: write\n  pull-requests: write\n"
    return ""


def membership_token_line(options: InitOptions) -> str:
    """Return the membership-token workflow input line when configured."""
    if not has_team_principals(options.allow) or not options.membership_token_secret:
        return ""
    return (
        "          membership-token: "
        f"${{{{ secrets.{options.membership_token_secret} }}}}\n"
    )


def apply_plan(plan: InitPlan, root: Path) -> None:
    """Write planned files to disk."""
    if has_team_principals(plan.options.allow):
        if (
            not plan.options.membership_token_secret
            and not plan.options.allow_default_membership_token
        ):
            raise GateError(
                "refusing to write team-principal workflows without "
                "--membership-token-secret; pass --allow-default-membership-token "
                "only if you intentionally accept fail-closed default-token behavior"
            )

    updates = tuple(file.path for file in plan.files if file.status(root) == "update")
    if updates and not plan.options.force:
        first = updates[0]
        raise GateError(
            f"refusing to overwrite {first}; rerun with --force or edit manually"
        )

    for file in plan.files:
        full_path = root / file.path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(file.content, encoding="utf-8")
