#!/usr/bin/env bash
# Shared fixtures for template tests.

# Run a repo task through mise so tests exercise the real task path.
template() {
  cd "$REPO_DIR" && mise run -q "$@"
}
export -f template
