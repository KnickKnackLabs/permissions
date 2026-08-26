#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

write_passing_test() {
  local path="$1" name="$2"
  mkdir -p "$(dirname "$path")"
  local test_keyword='@test'
  printf '%s\n' \
    '#!/usr/bin/env bats' \
    "$test_keyword \"$name\" {" \
    '  true' \
    '}' > "$path"
}

@test "options-only calls use the configured Permissions test directory" {
  run permissions test --jobs 1 \
    --filter '^allows an explicitly configured pull request author$'

  [ "$status" -eq 0 ]
  [[ "$output" == *'1..1'* ]]
  [[ "$output" == *'ok 1 allows an explicitly configured pull request author'* ]]
}

@test "an explicit BATS target takes precedence over the configured default" {
  local target="$BATS_TEST_TMPDIR/explicit.bats"
  write_passing_test "$target" 'explicit target only'

  run permissions test --jobs 1 "$target"

  [ "$status" -eq 0 ]
  [[ "$output" == *'1..1'* ]]
  [[ "$output" == *'ok 1 explicit target only'* ]]
}

@test "relative BATS targets resolve from the repository root" {
  run permissions test --jobs 1 test/pull_request_gate.bats \
    --filter '^allows an explicitly configured pull request author$'

  [ "$status" -eq 0 ]
  [[ "$output" == *'1..1'* ]]
  [[ "$output" == *'ok 1 allows an explicitly configured pull request author'* ]]
}

@test "whitespace-bearing explicit BATS targets remain one argument" {
  local target="$BATS_TEST_TMPDIR/explicit target/passing test.bats"
  write_passing_test "$target" 'whitespace target'

  run permissions test --jobs 1 "$target"

  [ "$status" -eq 0 ]
  [[ "$output" == *'1..1'* ]]
  [[ "$output" == *'ok 1 whitespace target'* ]]
}

@test "no-argument test task runs BATS before Python tests" {
  local mock_dir="$BATS_TEST_TMPDIR/mock-bin"
  local real_mise
  real_mise="$(command -v mise)"
  mkdir -p "$mock_dir"

  cat > "$mock_dir/bats" <<'SH'
#!/usr/bin/env bash
printf 'bats-default=%s\n' "$BATS_DEFAULT_TEST_TARGET"
printf 'bats-arg=%s\n' "$@"
SH
  cat > "$mock_dir/mise" <<'SH'
#!/usr/bin/env bash
printf 'python-arg=%s\n' "$@"
SH
  chmod +x "$mock_dir/bats" "$mock_dir/mise"

  PATH="$mock_dir:$PATH" run "$real_mise" -C "$REPO_DIR" run test

  [ "$status" -eq 0 ]
  [[ "$output" == *"bats-default=$REPO_DIR/test"* ]]
  [[ "$output" == *'bats-arg=--print-output-on-failure'* ]]
  [[ "$output" == *'python-arg=python:test'* ]]
  [[ "$output" == *'bats-default='*'python-arg='* ]]
}

@test "public Permissions test path remains serial by default" {
  local target="$BATS_TEST_TMPDIR/serial.bats"
  export PROBE_DIR="$BATS_TEST_TMPDIR/serial-barrier"
  mkdir -p "$PROBE_DIR"
  local test_keyword='@test'

  cat > "$target" <<BATS
#!/usr/bin/env bats
$test_keyword "first test runs alone" {
  touch "\$PROBE_DIR/one"
  sleep 0.2
  [ ! -e "\$PROBE_DIR/two" ]
  rm "\$PROBE_DIR/one"
}
$test_keyword "second test runs alone" {
  touch "\$PROBE_DIR/two"
  sleep 0.2
  [ ! -e "\$PROBE_DIR/one" ]
  rm "\$PROBE_DIR/two"
}
BATS

  run permissions test "$target"

  [ "$status" -eq 0 ]
}
