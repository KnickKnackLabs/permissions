#!/usr/bin/env bats

load test_helper

setup() {
  setup_workdir
}

@test "init fails non-interactively when required inputs are missing" {
  run permissions init --no-interactive

  [ "$status" -eq 2 ]
  [[ "$output" == *"stdin is not a TTY"* ]]
  [[ "$output" == *"--gate"* ]]
}

@test "init previews policy and workflows as JSON" {
  run permissions init \
    --gate issue \
    --gate pull-request \
    --allow user:rikonor \
    --on-deny close \
    --json

  [ "$status" -eq 0 ]
  python - "$output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["write"] is False
assert payload["gates"] == ["issue", "pull-request"]
assert {item["path"] for item in payload["files"]} == {
    "permissions.toml",
    ".github/workflows/permissions-issue-gate.yml",
    ".github/workflows/permissions-pull-request-gate.yml",
}
PY
  [ ! -e "$WORK_DIR/permissions.toml" ]
}

@test "init writes files in the caller workspace" {
  run permissions init \
    --gate issue \
    --allow user:rikonor \
    --on-deny fail \
    --write

  [ "$status" -eq 0 ]
  [ -f "$WORK_DIR/permissions.toml" ]
  [ -f "$WORK_DIR/.github/workflows/permissions-issue-gate.yml" ]
  [[ "$(cat "$WORK_DIR/permissions.toml")" == *"user:rikonor"* ]]
}

@test "init refuses to overwrite without force" {
  cat > "$WORK_DIR/permissions.toml" <<'TOML'
[gate.issue]
default = "allow"
TOML

  run permissions init \
    --gate issue \
    --allow user:rikonor \
    --on-deny fail \
    --write

  [ "$status" -eq 2 ]
  [[ "$output" == *"refusing to overwrite permissions.toml"* ]]
}

@test "init requires a membership secret before writing team workflows" {
  run permissions init \
    --gate issue \
    --allow team:KnickKnackLabs/agents \
    --on-deny fail \
    --write

  [ "$status" -eq 2 ]
  [[ "$output" == *"--membership-token-secret"* ]]
}
