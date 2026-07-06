# Contributing

`permissions` is a small KnickKnackLabs policy tool.
The first supported behavior is a GitHub pull request contribution gate:

```bash
mise run gate:pull-request --config permissions.toml --event event.json
```

Keep contribution gates separate from native access reconciliation.
This repo currently evaluates metadata only.
It must not checkout or execute untrusted pull request code in `pull_request_target` workflows.

## Structure

```text
permissions/
├── mise.toml                         # Tools, settings, codebase lint config
├── permissions.toml                  # Example pull request gate policy
├── README.tsx                        # Source for generated README.md
├── README.md                         # Generated; keep in sync with README.tsx
├── CONTRIBUTING.md                   # Repo orientation surface
├── .mise/tasks/test/_default         # Full suite runner for `mise run test`
├── .mise/tasks/doctor                # Local health checks and optional hook status
├── .mise/tasks/gate/pull-request     # Thin uv wrapper for the first gate command
├── .mise/tasks/test/python           # Python unit tests for helper code
├── .mise/tasks/lint/python           # Ruff check for Python task/library/test code
├── lib/permissions.py                # Shared gate parsing/evaluation/output helpers
└── test/                             # BATS integration tests plus Python unit tests
```

## Local setup

```bash
mise trust
mise install
mise run test
mise run doctor
```

`doctor` reports whether the optional local `codebase pre-commit` hook is installed.
Install it in your clone when you want convention lints to run before every commit:

```bash
codebase pre-commit
```

The hook lives under `.git/hooks/`, so it is intentionally not tracked by the repo.

## README workflow

Edit `README.tsx`, then regenerate and check the output:

```bash
readme build
readme build --check
```

CI also checks that `README.md` matches `README.tsx`.

## Gate scope

The first gate slice supports only explicit GitHub users in this form:

```toml
[gate.pull_request]
default = "deny"
allow = ["user:rikonor", "user:brownie-ricon"]
```

Do not add team expansion, collaborator reconciliation, revocation, GitLab, sourcehut, comments, labels, or close behavior in this slice.
Unsupported principal types should fail loudly until the policy model is intentionally widened.

## Validation before merge

```bash
mise run test
mise run lint:python
mise run doctor
codebase lint "$PWD"
readme build --check
git diff --check
```
