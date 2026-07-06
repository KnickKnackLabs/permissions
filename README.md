<div align="center">

# permissions

**Evaluate repository contribution policy before a pull request gets trusted.**

A small gate first, broader access reconciliation later.

![gate: pull_request](https://img.shields.io/badge/gate-pull__request-7c3aed?style=flat)
![shape: mise + BATS](https://img.shields.io/badge/shape-mise%20%2B%20BATS-4EAA25?style=flat&logo=gnubash&logoColor=white)
[![tests: 19](https://img.shields.io/badge/tests-19-brightgreen?style=flat)](test/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)

</div>

<br />

## What this is

`permissions` is a config-driven policy tool for repository stewardship. The first slice is a pull request gate: read GitHub event metadata, read `permissions.toml`, and exit with a verdict about the pull request author.

Contribution gates answer “may this event proceed?” Access reconciliation answers “what native forge permissions should exist?” This repo starts with the gate because it can run safely from event metadata before broader access commands exist.

## Quick start

```bash
cat > permissions.toml <<'TOML'
[gate.pull_request]
default = "deny"
allow = ["user:rikonor", "user:brownie-ricon"]
message = "This repo only accepts pull requests from configured principals."
TOML

# GitHub writes this shape to $GITHUB_EVENT_PATH in pull request workflows.
cat > event.json <<'JSON'
{"pull_request":{"user":{"login":"brownie-ricon"}}}
JSON

# This first PR is unreleased, so run the repo-local mise task directly:
mise run gate:pull-request --config permissions.toml --event event.json
mise run gate:pull-request --config permissions.toml --event event.json --json
```

## Gate behavior

This first policy model supports only explicit GitHub users. Allow entries use the `user:<login>` form. Unknown users receive a deny verdict. Unsupported principal types such as teams are rejected as malformed policy so the gate cannot accidentally overclaim support.

```toml
[gate.pull_request]
default = "deny"
allow = [
  "user:rikonor",
  "user:brownie-ricon",
]
message = "This repo only accepts pull requests from configured principals."
```

| Case            | Exit | Meaning                                                           |
| --------------- | ---- | ----------------------------------------------------------------- |
| Allowed author  | `0`  | The author matched a configured `user:<login>` principal.         |
| Denied author   | `1`  | The event was readable, but the author was outside the allowlist. |
| Malformed input | `2`  | The config or event shape was invalid for this gate.              |

## Workflow safety

The included `pull_request_target` workflow runs the metadata gate only. It checks out the base branch version of this repository, reads GitHub's event JSON from `$GITHUB_EVENT_PATH`, and leaves pull request head code untouched.

## Local development

1. Run `mise trust` after cloning.
2. Run `mise install` to install BATS, uv, codebase, and readme.
3. Use `mise run test` for the full local suite.
4. Use `mise run test:python` when iterating only on policy helper unit tests.
5. Use `mise run lint:python` for Ruff checks.
6. Use `mise run doctor` to check README freshness, convention lints, and optional hook state.
7. Regenerate docs with `readme build` after editing `README.tsx`.

## Validation

```bash
mise run test
mise run lint:python
mise run doctor
codebase lint "$PWD"
readme build --check
git diff --check
```

The suite currently has **19 tests** across CLI integration and policy helper coverage. The count is read from the repo at README build time.

<div align="center">

---

<sub>
This README was generated from `README.tsx` with [KnickKnackLabs/readme](https://github.com/KnickKnackLabs/readme).<br />Trust metadata before you trust code.
</sub></div>
