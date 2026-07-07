#!/usr/bin/env bats

load test_helper

setup() {
  setup_workdir
  write_policy "$WORK_DIR/permissions.toml"
}

@test "action task allows configured pull request authors" {
  write_event "$WORK_DIR/event.json" "rikonor"
  output_file="$WORK_DIR/github-output"

  export GITHUB_OUTPUT="$output_file"
  export GITHUB_WORKSPACE="$WORK_DIR"
  export INPUT_CONFIG="permissions.toml"
  export INPUT_EVENT="event.json"
  export INPUT_GATE="pull-request"
  export INPUT_ON_DENY="fail"

  run permissions action

  [ "$status" -eq 0 ]
  [[ "$output" == *"allowed: pull request author user:rikonor"* ]]
  [[ "$(cat "$output_file")" == *"allowed=true"* ]]
  [[ "$(cat "$output_file")" == *"gate=pull-request"* ]]
}

@test "action task fails denied issue authors" {
  write_issue_event "$WORK_DIR/event.json" "stranger"
  output_file="$WORK_DIR/github-output"

  export GITHUB_OUTPUT="$output_file"
  export GITHUB_WORKSPACE="$WORK_DIR"
  export INPUT_CONFIG="permissions.toml"
  export INPUT_EVENT="event.json"
  export INPUT_GATE="issue"
  export INPUT_ON_DENY="fail"

  run permissions action

  [ "$status" -eq 1 ]
  [[ "$output" == *"denied: issue author user:stranger"* ]]
  [[ "$(cat "$output_file")" == *"allowed=false"* ]]
  [[ "$(cat "$output_file")" == *"actor=user:stranger"* ]]
}
