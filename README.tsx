/** @jsxImportSource jsx-md */

import { existsSync, readFileSync, readdirSync } from "fs";
import { join, resolve } from "path";

import {
  Badge,
  Badges,
  Bold,
  Cell,
  Center,
  Code,
  CodeBlock,
  HR,
  Heading,
  Item,
  LineBreak,
  Link,
  List,
  Paragraph,
  Raw,
  Section,
  Sub,
  Table,
  TableHead,
  TableRow,
} from "readme";

const PROJECT = {
  name: "permissions",
  oneLine: "Evaluate repository contribution policy before a pull request gets trusted.",
  tagline: "A small gate first, broader access reconciliation later.",
  license: "MIT",
};

const REPO_DIR = resolve(import.meta.dirname);
const TEST_DIR = join(REPO_DIR, "test");

function read(path: string): string {
  return readFileSync(path, "utf8");
}

function walkFiles(dir: string, predicate: (path: string) => boolean): string[] {
  if (!existsSync(dir)) return [];

  const results: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkFiles(full, predicate));
    } else if (predicate(full)) {
      results.push(full);
    }
  }
  return results;
}

function countTests(): number {
  const batsTests = walkFiles(TEST_DIR, (path) => path.endsWith(".bats"))
    .map(read)
    .join("\n")
    .match(/@test\s+"/g)?.length ?? 0;

  const pythonTests = walkFiles(TEST_DIR, (path) => path.endsWith("_test.py"))
    .map(read)
    .join("\n")
    .match(/^\s*def test_/gm)?.length ?? 0;

  return batsTests + pythonTests;
}

const testCount = countTests();

const readme = (
  <>
    <Center>
      <Heading level={1}>{PROJECT.name}</Heading>

      <Paragraph>
        <Bold>{PROJECT.oneLine}</Bold>
      </Paragraph>

      <Paragraph>{PROJECT.tagline}</Paragraph>

      <Badges>
        <Badge label="gate" value="pull_request" color="7c3aed" />
        <Badge label="shape" value="mise + BATS" color="4EAA25" logo="gnubash" logoColor="white" />
        <Badge label="tests" value={`${testCount}`} color="brightgreen" href="test/" />
        <Badge label="License" value={PROJECT.license} color="blue" href="LICENSE" />
      </Badges>
    </Center>

    <LineBreak />

    <Section title="What this is">
      <Paragraph>
        <Code>permissions</Code>
        {" is a config-driven policy tool for repository stewardship. The first slice is a pull request gate: read GitHub event metadata, read "}
        <Code>permissions.toml</Code>
        {", and exit with a verdict about the pull request author."}
      </Paragraph>

      <Paragraph>
        {"Contribution gates answer “may this event proceed?” Access reconciliation answers “what native forge permissions should exist?” This repo starts with the gate because it can run safely from event metadata before broader access commands exist."}
      </Paragraph>
    </Section>

    <Section title="Quick start">
      <CodeBlock lang="bash">{`cat > permissions.toml <<'TOML'
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
mise run gate:pull-request --config permissions.toml --event event.json --json`}</CodeBlock>
    </Section>

    <Section title="Gate behavior">
      <Paragraph>
        {"This first policy model supports only explicit GitHub users. Allow entries use the "}
        <Code>user:&lt;login&gt;</Code>
        {" form. Unknown users receive a deny verdict. Unsupported principal types such as teams are rejected as malformed policy so the gate cannot accidentally overclaim support."}
      </Paragraph>

      <CodeBlock lang="toml">{`[gate.pull_request]
default = "deny"
allow = [
  "user:rikonor",
  "user:brownie-ricon",
]
message = "This repo only accepts pull requests from configured principals."`}</CodeBlock>

      <Table>
        <TableHead>
          <Cell>Case</Cell>
          <Cell>Exit</Cell>
          <Cell>Meaning</Cell>
        </TableHead>
        <TableRow>
          <Cell>Allowed author</Cell>
          <Cell><Code>0</Code></Cell>
          <Cell>The author matched a configured <Code>user:&lt;login&gt;</Code> principal.</Cell>
        </TableRow>
        <TableRow>
          <Cell>Denied author</Cell>
          <Cell><Code>1</Code></Cell>
          <Cell>The event was readable, but the author was outside the allowlist.</Cell>
        </TableRow>
        <TableRow>
          <Cell>Malformed input</Cell>
          <Cell><Code>2</Code></Cell>
          <Cell>The config or event shape was invalid for this gate.</Cell>
        </TableRow>
      </Table>
    </Section>

    <Section title="Workflow safety">
      <Paragraph>
        {"The included "}
        <Code>pull_request_target</Code>
        {" workflow runs the metadata gate only. It checks out the base branch version of this repository, reads GitHub's event JSON from "}
        <Code>$GITHUB_EVENT_PATH</Code>
        {", and leaves pull request head code untouched."}
      </Paragraph>
    </Section>

    <Section title="Local development">
      <List ordered>
        <Item>Run <Code>mise trust</Code> after cloning.</Item>
        <Item>Run <Code>mise install</Code> to install BATS, uv, codebase, and readme.</Item>
        <Item>Use <Code>mise run test</Code> for the full local suite.</Item>
        <Item>Use <Code>mise run test:python</Code> when iterating only on policy helper unit tests.</Item>
        <Item>Use <Code>mise run lint:python</Code> for Ruff checks.</Item>
        <Item>Use <Code>mise run doctor</Code> to check README freshness, convention lints, and optional hook state.</Item>
        <Item>Regenerate docs with <Code>readme build</Code> after editing <Code>README.tsx</Code>.</Item>
      </List>
    </Section>

    <Section title="Validation">
      <CodeBlock lang="bash">{`mise run test
mise run lint:python
mise run doctor
codebase lint "$PWD"
readme build --check
git diff --check`}</CodeBlock>

      <Paragraph>
        {"The suite currently has "}
        <Bold>{`${testCount} tests`}</Bold>
        {" across CLI integration and policy helper coverage. The count is read from the repo at README build time."}
      </Paragraph>
    </Section>

    <Center>
      <HR />
      <Sub>
        {"This README was generated from "}
        <Code>README.tsx</Code>
        {" with "}
        <Link href="https://github.com/KnickKnackLabs/readme">KnickKnackLabs/readme</Link>
        {"."}
        <Raw>{"<br />"}</Raw>
        {"Trust metadata before you trust code."}
      </Sub>
    </Center>
  </>
);

console.log(readme);
