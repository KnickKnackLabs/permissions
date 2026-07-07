#!/usr/bin/env bats

load test_helper

setup() {
  setup_workdir
  write_policy "$WORK_DIR/permissions.toml"
}

@test "allows an explicitly configured issue author" {
  write_issue_event "$WORK_DIR/event.json" "brownie-ricon"

  run permissions gate issue --config permissions.toml --event event.json

  [ "$status" -eq 0 ]
  [[ "$output" == *"allowed"* ]]
  [[ "$output" == *"issue author user:brownie-ricon"* ]]
}

@test "denies an unconfigured issue author" {
  write_issue_event "$WORK_DIR/event.json" "stranger"

  run permissions gate issue --config permissions.toml --event event.json

  [ "$status" -eq 1 ]
  [[ "$output" == *"denied"* ]]
  [[ "$output" == *"user:stranger is not in gate.issue.allow"* ]]
}

@test "emits JSON issue verdicts" {
  write_issue_event "$WORK_DIR/event.json" "rikonor"

  run permissions gate issue --config permissions.toml --event event.json --json

  [ "$status" -eq 0 ]
  python - "$output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["allowed"] is True
assert payload["actor"] == "user:rikonor"
assert payload["gate"] == "issue"
assert payload["login"] == "rikonor"
PY
}

@test "rejects pull request conversation events for issue gates" {
  cat > "$WORK_DIR/event.json" <<'JSON'
{"issue":{"number":9,"pull_request":{"url":"https://api.github.com/repos/o/r/pulls/9"},"user":{"login":"rikonor"}}}
JSON

  run permissions gate issue --config permissions.toml --event event.json

  [ "$status" -eq 2 ]
  [[ "$output" == *"issue gate does not evaluate pull request conversation events"* ]]
}

@test "allows by default when configured" {
  cat > "$WORK_DIR/permissions.toml" <<'TOML'
[gate.issue]
default = "allow"
deny = ["user:blocked"]
TOML
  write_issue_event "$WORK_DIR/event.json" "newcomer"

  run permissions gate issue --config permissions.toml --event event.json

  [ "$status" -eq 0 ]
  [[ "$output" == *"gate.issue.default is allow"* ]]
}

@test "denies explicit deny entries when default allows" {
  cat > "$WORK_DIR/permissions.toml" <<'TOML'
[gate.issue]
default = "allow"
deny = ["user:blocked"]
TOML
  write_issue_event "$WORK_DIR/event.json" "blocked"

  run permissions gate issue --config permissions.toml --event event.json

  [ "$status" -eq 1 ]
  [[ "$output" == *"matched deny entry user:blocked"* ]]
}
