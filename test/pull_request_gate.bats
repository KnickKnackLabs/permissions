#!/usr/bin/env bats

load test_helper

setup() {
  setup_workdir
  write_policy "$WORK_DIR/permissions.toml"
}

@test "allows an explicitly configured pull request author" {
  write_event "$WORK_DIR/event.json" "brownie-ricon"

  run permissions gate pull-request --config permissions.toml --event event.json

  [ "$status" -eq 0 ]
  [[ "$output" == *"allowed"* ]]
  [[ "$output" == *"user:brownie-ricon"* ]]
}

@test "denies an unconfigured pull request author" {
  write_event "$WORK_DIR/event.json" "stranger"

  run permissions gate pull-request --config permissions.toml --event event.json

  [ "$status" -eq 1 ]
  [[ "$output" == *"denied"* ]]
  [[ "$output" == *"user:stranger is not in gate.pull_request.allow"* ]]
}

@test "emits JSON verdicts" {
  write_event "$WORK_DIR/event.json" "rikonor"

  run permissions gate pull-request --config permissions.toml --event event.json --json

  [ "$status" -eq 0 ]
  python - "$output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["allowed"] is True
assert payload["actor"] == "user:rikonor"
assert payload["login"] == "rikonor"
PY
}

@test "reports malformed events" {
  printf '{"pull_request": {"user": {}}}' > "$WORK_DIR/event.json"

  run permissions gate pull-request --config permissions.toml --event event.json

  [ "$status" -eq 2 ]
  [[ "$output" == *"event is missing pull_request.user.login"* ]]
}

@test "rejects unsupported principal types in the first slice" {
  cat > "$WORK_DIR/permissions.toml" <<'TOML'
[gate.pull_request]
default = "deny"
allow = ["team:KnickKnackLabs/agents"]
TOML
  write_event "$WORK_DIR/event.json" "brownie-ricon"

  run permissions gate pull-request --config permissions.toml --event event.json

  [ "$status" -eq 2 ]
  [[ "$output" == *"unsupported principals"* ]]
  [[ "$output" == *"team:KnickKnackLabs/agents"* ]]
}

@test "README.md is generated from README.tsx" {
  run bash -c 'cd "$REPO_DIR" && readme build --check'
  [ "$status" -eq 0 ]
}

@test "doctor reports optional pre-commit hook state" {
  run permissions doctor
  [ "$status" -eq 0 ]
  [[ "$output" == *"pre-commit"* ]]
}
