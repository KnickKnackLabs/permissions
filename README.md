<div align="center">

# permissions

**Evaluate repository contribution policy before public events get trusted.**

Keep the repo public. Gate the event metadata before trusting the event.

![gates: pull_request + issue](https://img.shields.io/badge/gates-pull__request%20%2B%20issue-7c3aed?style=flat)
![action: mise-backed](https://img.shields.io/badge/action-mise--backed-0ea5e9?style=flat)
[![tests: 81](https://img.shields.io/badge/tests-81-brightgreen?style=flat)](test/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)

</div>

<br />

## What this is

`permissions` is a config-driven policy gate for public repositories that want open visibility but restricted participation. It reads GitHub event metadata, reads `permissions.toml`, and decides whether the event author is allowed for that gate.

The current gates are pull requests and issues. Access reconciliation can come later; this package starts with safe event gates because they can run before any untrusted pull request code is checked out or executed.

## Quick start

```bash
shiv install permissions

cat > permissions.toml <<'TOML'
[gate.pull_request]
default = "deny"
allow = ["user:rikonor", "team:KnickKnackLabs/agents"]
message = "This repo only accepts pull requests from configured principals."

[gate.issue]
default = "deny"
allow = ["user:rikonor", "team:KnickKnackLabs/agents"]
message = "This repo only accepts issues from configured principals."
TOML

cat > event.json <<'JSON'
{"pull_request":{"number":2,"user":{"login":"brownie-ricon"}}}
JSON

permissions gate pull-request --config permissions.toml --event event.json
permissions gate pull-request --config permissions.toml --event event.json --json
```

## GitHub Action

Use the root Action as a gate job inside workflows that should not continue for unauthorized event authors.

```yaml
jobs:
  permissions:
    runs-on: ubuntu-latest
    steps:
      # Read trusted base-branch policy, not pull request head policy.
      - uses: actions/checkout@v6
        with:
          ref: ${{ github.event.pull_request.base.ref }}
      - uses: KnickKnackLabs/permissions@v0.4.0
        with:
          gate: pull-request
          on-deny: fail
          membership-token: ${{ secrets.PERMISSIONS_MEMBERSHIP_TOKEN }}

  test:
    needs: permissions
    runs-on: ubuntu-latest
    steps:
      # The PR code is checked out only after the gate allows the author.
      - uses: actions/checkout@v6
      - run: mise run test
```

For enforcement workflows that should close denied events, use `on-deny: close` with write-capable workflow permissions. A denied event is labeled `permissions-denied`, receives an explanatory comment, is closed, and the Action still fails, leaving a visible audit signal. Denied issues are closed as not planned; denied pull requests are closed normally because GitHub does not provide PR close reasons.

## Initialize a repo

`permissions init` previews or writes a starter `permissions.toml` plus standard issue and pull request gate workflows. It is dry-run by default; pass `--write` to mutate files.

```bash
permissions init   --gate issue   --gate pull-request   --allow user:rikonor   --allow team:KnickKnackLabs/agents   --on-deny close   --membership-token-secret PERMISSIONS_MEMBERSHIP_TOKEN

permissions init   --gate issue   --allow user:rikonor   --on-deny fail   --write
```

When team principals are present, init prints token setup guidance. Store a token with `read:org` as the named membership secret, then generated workflows pass it to the Action. In non-interactive shells, init requires the needed flags and exits with an actionable error instead of prompting.

## Policy model

Each gate has a default posture plus explicit principal lists. `deny` entries win first, then `allow` entries, then the configured `default` fallback. This supports both fail-closed allowlists and fail-open deny lists.

```toml
[gate.pull_request]
default = "deny"
allow = [
  "user:rikonor",
  "team:KnickKnackLabs/agents",
]
message = "This repo only accepts pull requests from configured principals."

[gate.issue]
default = "allow"
deny = [
  "user:spammy-mcspamface",
]
message = "This issue was closed by repository policy."
```

This release supports explicit GitHub users with `user:<login>` principals and GitHub teams with `team:<org>/<team-slug>` principals. Team principals require a token that can read organization team membership; if team membership cannot be resolved, the gate fails closed.

| Case            | Exit | Meaning                                                                       |
| --------------- | ---- | ----------------------------------------------------------------------------- |
| Allowed author  | `0`  | The author matched `allow` or the gate default is `allow`.                    |
| Denied author   | `1`  | The author matched `deny` or missed the allowlist when the default is `deny`. |
| Malformed input | `2`  | The config, gate name, event shape, or deny behavior is invalid.              |

## Workflow safety

A permissions gate should read trusted base-repo policy and GitHub event metadata only. In pull request workflows, checkout the base branch before running this Action; otherwise an untrusted PR author could edit `permissions.toml` in their branch and allow themselves. If a pull request workflow uses `pull_request_target` so it can close denied PRs, it must not checkout or execute pull request head code.

Team principals are resolved with the `membership-token` Action input. Use a token with read access to the relevant organization teams. If omitted, the Action falls back to `github-token` and then GitHub's default workflow token.

When `on-deny: close` is used for pull requests, grant both `pull-requests: write` and `issues: write` so the Action can close the PR, apply labels, and comment on the PR conversation.

Separate GitHub workflow files run independently. If a test, build, or deploy workflow should be protected by the gate, put the permissions Action inside that workflow and make the sensitive jobs depend on it with `needs`.

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

The suite currently has **81 tests** across CLI integration, Action behavior, and policy helper coverage. The count is read from the repo at README build time.

<div align="center">

---

<sub>
This README was generated from `README.tsx` with [KnickKnackLabs/readme](https://github.com/KnickKnackLabs/readme).<br />Trust metadata before you trust code.
</sub></div>
