"""CLI orchestration for permissions init."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

from permissions import GateError

from .models import (
    InitOptions,
    InitPlan,
    bool_from_env,
    options_from_env,
    validate_options,
)
from .prompts import confirm_overwrite, prompt_for_missing_options
from .render import apply_plan, build_plan


def run_from_env(env: dict[str, str], *, root: Path) -> int:
    """Run init from a mise task environment."""
    options = options_from_env(env)
    interactive = sys.stdin.isatty() and not bool_from_env(
        env.get("usage_no_interactive")
    )
    options = complete_options(options, interactive=interactive)
    plan = build_plan(options)
    status_overrides: dict[Path, str] | None = None
    if options.write:
        plan = maybe_confirm_overwrite(plan, root, interactive=interactive)
        status_overrides = write_statuses(plan, root)
        apply_plan(plan, root)
    print_plan(
        plan,
        root,
        json_output=bool_from_env(env.get("usage_json")),
        status_overrides=status_overrides,
    )
    return 0


def complete_options(options: InitOptions, *, interactive: bool) -> InitOptions:
    """Fill missing options interactively when available, otherwise validate."""
    if options.gates and options.allow and options.on_deny:
        return validate_options(options)
    if not interactive:
        missing = []
        if not options.gates:
            missing.append("--gate")
        if not options.allow:
            missing.append("--allow")
        if not options.on_deny:
            missing.append("--on-deny")
        raise GateError(
            "permissions init needs interactive input, but stdin is not a TTY. "
            f"Pass {', '.join(missing)} and --write, or run from a terminal."
        )
    return validate_options(prompt_for_missing_options(options))


def maybe_confirm_overwrite(
    plan: InitPlan, root: Path, *, interactive: bool
) -> InitPlan:
    """Confirm overwrites interactively and return an updated plan."""
    if plan.options.force:
        return plan
    updates = files_requiring_overwrite(plan, root)
    if not updates:
        return plan
    if not interactive:
        return plan
    if not confirm_overwrite(updates):
        raise GateError("refusing to overwrite existing files")
    forced_options = replace(plan.options, force=True)
    return build_plan(forced_options)


def files_requiring_overwrite(plan: InitPlan, root: Path) -> tuple[Path, ...]:
    """Return planned file paths that would update existing content."""
    return tuple(file.path for file in plan.files if file.status(root) == "update")


def write_statuses(plan: InitPlan, root: Path) -> dict[Path, str]:
    """Return post-write status labels based on the pre-write plan."""
    labels = {
        "create": "created",
        "update": "updated",
        "unchanged": "unchanged",
    }
    return {file.path: labels[file.status(root)] for file in plan.files}


def print_plan(
    plan: InitPlan,
    root: Path,
    *,
    json_output: bool = False,
    status_overrides: dict[Path, str] | None = None,
) -> None:
    """Print a human or JSON init plan."""
    if json_output:
        print(json.dumps(plan.to_json(root), indent=2, sort_keys=True))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    mode = "write" if plan.options.write else "dry-run"
    console.print(f"[bold]permissions init[/bold] ({mode})")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Status")
    table.add_column("Path")
    for file in plan.files:
        status = (
            status_overrides[file.path]
            if status_overrides is not None
            else file.status(root)
        )
        table.add_row(status, str(file.path))
    console.print(table)

    if plan.warnings:
        console.print("\n[bold yellow]Warnings[/bold yellow]")
        for warning in plan.warnings:
            console.print(f"- {warning}")

    if plan.guidance:
        console.print("\n[bold]Team token guidance[/bold]")
        for item in plan.guidance:
            console.print(f"- {item}")
