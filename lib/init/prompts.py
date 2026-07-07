"""Interactive prompts for permissions init."""

from __future__ import annotations

from pathlib import Path

from .models import DEFAULT_MEMBERSHIP_SECRET, InitOptions, has_team_principals


def confirm_overwrite(paths: tuple[Path, ...]) -> bool:
    """Ask whether existing files may be overwritten."""
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()
    console.print("\n[bold yellow]Existing files would be updated:[/bold yellow]")
    for path in paths:
        console.print(f"- {path}")
    return Confirm.ask("Overwrite these files?", default=False)


def prompt_for_missing_options(options: InitOptions) -> InitOptions:
    """Prompt for missing init options in a terminal."""
    from rich.prompt import Confirm, Prompt

    gates = options.gates
    if not gates:
        gates_text = Prompt.ask(
            "Gates to install (comma-separated: issue, pull-request)",
            default="issue,pull-request",
        )
        gates = tuple(item.strip() for item in gates_text.split(",") if item.strip())

    allow = options.allow
    if not allow:
        allow_text = Prompt.ask(
            "Allowed principals (comma-separated user:<login> or team:<org>/<slug>)",
            default="user:rikonor",
        )
        allow = tuple(item.strip() for item in allow_text.split(",") if item.strip())

    on_deny = options.on_deny
    if not on_deny:
        on_deny = Prompt.ask(
            "Deny behavior",
            choices=["close", "fail"],
            default="close",
        )

    membership_secret = options.membership_token_secret
    if has_team_principals(allow) and not membership_secret:
        membership_secret = Prompt.ask(
            "Membership token secret name (blank means default workflow token)",
            default=DEFAULT_MEMBERSHIP_SECRET,
        )

    write = options.write
    if not write:
        write = Confirm.ask("Write permissions files now?", default=False)

    return InitOptions(
        gates=gates,
        allow=allow,
        on_deny=on_deny,
        action_ref=options.action_ref,
        membership_token_secret=membership_secret,
        write=write,
        force=options.force,
        allow_default_membership_token=options.allow_default_membership_token,
    )
