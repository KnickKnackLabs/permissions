<div align="center">

# template

**A sane starting point for small KnickKnackLabs tools.**

Copy the boring parts so the interesting parts start sooner.

![shape: mise + BATS](https://img.shields.io/badge/shape-mise%20%2B%20BATS-4EAA25?style=flat&logo=gnubash&logoColor=white)
[![tests: 3](https://img.shields.io/badge/tests-3-brightgreen?style=flat)](test/)
![lints: 9](https://img.shields.io/badge/lints-9-blue?style=flat)
![README: TSX](https://img.shields.io/badge/README-TSX-f472b6?style=flat)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)

</div>

<br />

## What this is

`template` is the default empty room for a new KnickKnackLabs tool: mise-managed tasks, BATS tests, codebase convention lints, generated README, CI, and a `doctor` task that tells you whether your clone has the optional local pre-commit hook installed.

This is deliberately a normal repo, not a GitHub template repo. Copy the files, start fresh history for the new tool, and keep this repo as the living reference skeleton.

It intentionally does **not** decide what your product does. Copy it, rename the obvious constants, then add the first real command only when the workflow is clear.

## Quick start

```bash
gh repo clone KnickKnackLabs/template my-tool
cd my-tool

# Start the new tool with its own history instead of inheriting template commits.
rm -rf .git
git init -b main

mise trust
mise install
mise run test
mise run doctor

# Optional local safety net: installs .git/hooks/pre-commit.d/codebase
codebase pre-commit

# When the skeleton is shaped for the new tool, create and push its repo.
git add .
git commit -m "chore: start from KKL tool skeleton"
gh repo create KnickKnackLabs/my-tool --public --source=. --remote=origin --push
```

## Goodies baked in

| Goodie            | Why it exists                                                                                            | Where                        |
| ----------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Generated README  | TSX can count tests, list tasks, and keep docs honest in CI.                                             | `README.tsx`                 |
| Doctor hook check | Local pre-commit hooks are clone-local, so the repo can report them without pretending they are tracked. | `mise run doctor`            |
| Convention lints  | Best-practice drift gets caught as code, not folklore.                                                   | `[_.codebase].lint`          |
| Real test path    | BATS tests call tasks through `mise run`, not raw scripts.                                               | `test/test_helper.bash`      |
| Mac + Linux CI    | Bash and tooling differences show up before merge.                                                       | ubuntu-latest + macos-latest |

## Scaffold inventory

| Path                         | Status | Purpose                                     |
| ---------------------------- | ------ | ------------------------------------------- |
| `mise.toml`                  | ✓      | tools, settings, and codebase lint config   |
| `README.tsx`                 | ✓      | programmable README source                  |
| `CONTRIBUTING.md`            | ✓      | repo-entry orientation surface              |
| `.mise/tasks/test`           | ✓      | canonical BATS runner                       |
| `.mise/tasks/doctor`         | ✓      | local health check plus hook hint           |
| `.github/workflows/test.yml` | ✓      | Ubuntu/macOS CI                             |
| `test/`                      | ✓      | BATS smoke coverage                         |
| `lib/`                       | ✓      | shared runtime code starts here when needed |

## Tasks

| Task              | Description                   |
| ----------------- | ----------------------------- |
| `mise run doctor` | Check local development setup |
| `mise run test`   | Run BATS tests                |

## When you copy it

1. Rename `PROJECT` in `README.tsx`.
2. Rewrite this README around the actual tool, but keep the dynamic counters if they help.
3. Replace `CONTRIBUTING.md` with repo-specific orientation.
4. Add real task files under `.mise/tasks/`; use `$MISE_CONFIG_ROOT` inside tasks only.
5. Put shared Bash helpers in `lib/` only once multiple tasks need them.
6. If the installed tool resolves caller-relative paths, read the shiv-provided `<PACKAGE>_CALLER_PWD` variable, not generic `CALLER_PWD`.

<details>
<summary><b>Current convention checks</b></summary>

This template currently asks [codebase](https://github.com/KnickKnackLabs/codebase) to run these lint rules:

```
mise-settings
bats-test-helper
bats-test-task
mcr-scope
or-true
shellcheck
gum-table
caller-pwd-contract
github-actions
```

</details>

## Validation

```bash
mise run test
codebase lint "$PWD"
readme build --check
git diff --check
```

The starter suite currently has **3 tests** and **2 public tasks**. Those numbers are read from the repo at README build time.

<div align="center">

---

<sub>
This README was generated from `README.tsx` with [KnickKnackLabs/readme](https://github.com/KnickKnackLabs/readme).<br />A skeleton is a kindness to whoever has to remember the boring parts tomorrow.
</sub></div>
