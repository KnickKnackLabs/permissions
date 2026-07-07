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
  oneLine: "Evaluate repository contribution policy before public events get trusted.",
  tagline: "Keep the repo public. Gate the event metadata before trusting the event.",
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
        <Badge label="gates" value="pull_request + issue" color="7c3aed" />
        <Badge label="action" value="mise-backed" color="0ea5e9" />
        <Badge label="tests" value={`${testCount}`} color="brightgreen" href="test/" />
        <Badge label="License" value={PROJECT.license} color="blue" href="LICENSE" />
      </Badges>
    </Center>

    <LineBreak />

    <Section title="What this is">
      <Paragraph>
        <Code>permissions</Code>
        {" is a config-driven policy gate for public repositories that want open visibility but restricted participation. It reads GitHub event metadata, reads "}
        <Code>permissions.toml</Code>
        {", and decides whether the event author is allowed for that gate."}
      </Paragraph>

      <Paragraph>
        {"The current gates are pull requests and issues. Access reconciliation can come later; this package starts with safe event gates because they can run before any untrusted pull request code is checked out or executed."}
      </Paragraph>
    </Section>

    <Section title="Quick start">
      <CodeBlock lang="bash">{`shiv install permissions

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
permissions gate pull-request --config permissions.toml --event event.json --json`}</CodeBlock>
    </Section>

    <Section title="GitHub Action">
      <Paragraph>
        {"Use the root Action as a gate job inside workflows that should not continue for unauthorized event authors."}
      </Paragraph>

      <CodeBlock lang="yaml">{`jobs:
  permissions:
    runs-on: ubuntu-latest
    steps:
      # Read trusted base-branch policy, not pull request head policy.
      - uses: actions/checkout@v6
        with:
          ref: \${{ github.event.pull_request.base.ref }}
      - uses: KnickKnackLabs/permissions@v0.4.0
        with:
          gate: pull-request
          on-deny: fail
          membership-token: \${{ secrets.PERMISSIONS_MEMBERSHIP_TOKEN }}

  test:
    needs: permissions
    runs-on: ubuntu-latest
    steps:
      # The PR code is checked out only after the gate allows the author.
      - uses: actions/checkout@v6
      - run: mise run test`}</CodeBlock>

      <Paragraph>
        {"For enforcement workflows that should close denied events, use "}
        <Code>on-deny: close</Code>
        {" with write-capable workflow permissions. A denied event is labeled "}
        <Code>permissions-denied</Code>
        {", receives an explanatory comment, is closed, and the Action still fails, leaving a visible audit signal. Denied issues are closed as not planned; denied pull requests are closed normally because GitHub does not provide PR close reasons."}
      </Paragraph>
    </Section>

    <Section title="Initialize a repo">
      <Paragraph>
        <Code>permissions init</Code>
        {" previews or writes a starter "}
        <Code>permissions.toml</Code>
        {" plus standard issue and pull request gate workflows. It is dry-run by default; pass "}
        <Code>--write</Code>
        {" to mutate files."}
      </Paragraph>

      <CodeBlock lang="bash">{`permissions init \
  --gate issue \
  --gate pull-request \
  --allow user:rikonor \
  --allow team:KnickKnackLabs/agents \
  --on-deny close \
  --membership-token-secret PERMISSIONS_MEMBERSHIP_TOKEN

permissions init \
  --gate issue \
  --allow user:rikonor \
  --on-deny fail \
  --write`}</CodeBlock>

      <Paragraph>
        {"When team principals are present, init prints token setup guidance. Store a token with "}
        <Code>read:org</Code>
        {" as the named membership secret, then generated workflows pass it to the Action. In non-interactive shells, init requires the needed flags and exits with an actionable error instead of prompting."}
      </Paragraph>
    </Section>

    <Section title="Policy model">
      <Paragraph>
        {"Each gate has a default posture plus explicit principal lists. "}
        <Code>deny</Code>
        {" entries win first, then "}
        <Code>allow</Code>
        {" entries, then the configured "}
        <Code>default</Code>
        {" fallback. This supports both fail-closed allowlists and fail-open deny lists."}
      </Paragraph>

      <CodeBlock lang="toml">{`[gate.pull_request]
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
message = "This issue was closed by repository policy."`}</CodeBlock>

      <Paragraph>
        {"This release supports explicit GitHub users with "}
        <Code>user:&lt;login&gt;</Code>
        {" principals and GitHub teams with "}
        <Code>team:&lt;org&gt;/&lt;team-slug&gt;</Code>
        {" principals. Team principals require a token that can read organization team membership; if team membership cannot be resolved, the gate fails closed."}
      </Paragraph>

      <Table>
        <TableHead>
          <Cell>Case</Cell>
          <Cell>Exit</Cell>
          <Cell>Meaning</Cell>
        </TableHead>
        <TableRow>
          <Cell>Allowed author</Cell>
          <Cell><Code>0</Code></Cell>
          <Cell>The author matched <Code>allow</Code> or the gate default is <Code>allow</Code>.</Cell>
        </TableRow>
        <TableRow>
          <Cell>Denied author</Cell>
          <Cell><Code>1</Code></Cell>
          <Cell>The author matched <Code>deny</Code> or missed the allowlist when the default is <Code>deny</Code>.</Cell>
        </TableRow>
        <TableRow>
          <Cell>Malformed input</Cell>
          <Cell><Code>2</Code></Cell>
          <Cell>The config, gate name, event shape, or deny behavior is invalid.</Cell>
        </TableRow>
      </Table>
    </Section>

    <Section title="Workflow safety">
      <Paragraph>
        {"A permissions gate should read trusted base-repo policy and GitHub event metadata only. In pull request workflows, checkout the base branch before running this Action; otherwise an untrusted PR author could edit "}
        <Code>permissions.toml</Code>
        {" in their branch and allow themselves. If a pull request workflow uses "}
        <Code>pull_request_target</Code>
        {" so it can close denied PRs, it must not checkout or execute pull request head code."}
      </Paragraph>

      <Paragraph>
        {"Team principals are resolved with the "}
        <Code>membership-token</Code>
        {" Action input. Use a token with read access to the relevant organization teams. If omitted, the Action falls back to "}
        <Code>github-token</Code>
        {" and then GitHub's default workflow token."}
      </Paragraph>

      <Paragraph>
        {"When "}
        <Code>on-deny: close</Code>
        {" is used for pull requests, grant both "}
        <Code>pull-requests: write</Code>
        {" and "}
        <Code>issues: write</Code>
        {" so the Action can close the PR, apply labels, and comment on the PR conversation."}
      </Paragraph>

      <Paragraph>
        {"Separate GitHub workflow files run independently. If a test, build, or deploy workflow should be protected by the gate, put the permissions Action inside that workflow and make the sensitive jobs depend on it with "}
        <Code>needs</Code>
        {"."}
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
        {" across CLI integration, Action behavior, and policy helper coverage. The count is read from the repo at README build time."}
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
