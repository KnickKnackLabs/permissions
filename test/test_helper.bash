#!/usr/bin/env bash
# Shared fixtures for permissions tests.

# Run permissions tasks through mise so tests exercise the real task path.
permissions() {
  local args=("$@")
  if [ "${args[0]-}" = "gate" ] && [ -n "${args[1]-}" ]; then
    args[0]="gate:${args[1]}"
    args=("${args[0]}" "${args[@]:2}")
  fi

  cd "$REPO_DIR" && PERMISSIONS_CALLER_PWD="${PERMISSIONS_CALLER_PWD:-$PWD}" mise run -q "${args[@]}"
}
export -f permissions

write_policy() {
  local path="$1"
  cat > "$path" <<'TOML'
[gate.pull_request]
default = "deny"
allow = [
  "user:rikonor",
  "user:brownie-ricon",
]
message = "This repo only accepts pull requests from configured principals."

[gate.issue]
default = "deny"
allow = [
  "user:rikonor",
  "user:brownie-ricon",
]
message = "This repo only accepts issues from configured principals."
TOML
}

write_event() {
  local path="$1"
  local login="$2"
  python - "$path" "$login" <<'PY'
import json
import sys

path, login = sys.argv[1:]
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"pull_request": {"number": 2, "user": {"login": login}}}, fh)
PY
}

write_issue_event() {
  local path="$1"
  local login="$2"
  python - "$path" "$login" <<'PY'
import json
import sys

path, login = sys.argv[1:]
with open(path, "w", encoding="utf-8") as fh:
    json.dump({"issue": {"number": 7, "user": {"login": login}}}, fh)
PY
}

setup_workdir() {
  WORK_DIR="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK_DIR"
  export WORK_DIR
  export PERMISSIONS_CALLER_PWD="$WORK_DIR"
}
