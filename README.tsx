/** @jsxImportSource jsx-md */

import { existsSync, readFileSync, readdirSync, statSync } from "fs";
import { join, resolve } from "path";

import {
  Badge,
  Badges,
  Bold,
  Cell,
  Center,
  Code,
  CodeBlock,
  Details,
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
  name: "template",
  oneLine: "A sane starting point for small KnickKnackLabs tools.",
  tagline: "Copy the boring parts so the interesting parts start sooner.",
  license: "MIT",
};

const REPO_DIR = resolve(import.meta.dirname);
const TASK_DIR = join(REPO_DIR, ".mise/tasks");
const TEST_DIR = join(REPO_DIR, "test");
const WORKFLOW = join(REPO_DIR, ".github/workflows/test.yml");

interface TaskInfo {
  name: string;
  description: string;
}

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

function discoverTasks(dir = TASK_DIR, prefix = ""): TaskInfo[] {
  if (!existsSync(dir)) return [];

  const tasks: TaskInfo[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const full = join(dir, entry.name);
    const name = prefix ? `${prefix}:${entry.name}` : entry.name;

    if (entry.isDirectory()) {
      tasks.push(...discoverTasks(full, name));
      continue;
    }

    const mode = statSync(full).mode;
    if ((mode & 0o111) === 0) continue;

    const src = read(full);
    const description = src.match(/^#MISE description="(.+)"$/m)?.[1] ?? "";
    tasks.push({ name, description });
  }

  return tasks.sort((a, b) => a.name.localeCompare(b.name));
}

function countBatsTests(): number {
  return walkFiles(TEST_DIR, (path) => path.endsWith(".bats"))
    .map(read)
    .join("\n")
    .match(/@test\s+"/g)?.length ?? 0;
}

function configuredLints(): string[] {
  const miseToml = read(join(REPO_DIR, "mise.toml"));
  const start = miseToml.indexOf("[_.codebase]");
  if (start === -1) return [];

  const lines = miseToml.slice(start).split("\n");
  const block: string[] = [];
  for (const [index, line] of lines.entries()) {
    if (index > 0 && line.startsWith("[")) break;
    block.push(line);
  }

  const list = block.join("\n").match(/lint\s*=\s*\[([\s\S]*?)\]/)?.[1] ?? "";
  return [...list.matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

function workflowOses(): string[] {
  if (!existsSync(WORKFLOW)) return [];
  const match = read(WORKFLOW).match(/os:\s*\[([^\]]+)\]/);
  if (!match) return [];
  return match[1].split(",").map((os) => os.trim()).filter(Boolean);
}

function status(path: string): string {
  return existsSync(join(REPO_DIR, path)) ? "✓" : "missing";
}

const tasks = discoverTasks();
const testCount = countBatsTests();
const lints = configuredLints();
const oses = workflowOses();

const scaffold = [
  ["mise.toml", "tools, settings, and codebase lint config"],
  ["README.tsx", "programmable README source"],
  ["CONTRIBUTING.md", "repo-entry orientation surface"],
  [".mise/tasks/test", "canonical BATS runner"],
  [".mise/tasks/doctor", "local health check plus hook hint"],
  [".github/workflows/test.yml", "Ubuntu/macOS CI"],
  ["test/", "BATS smoke coverage"],
  ["lib/", "shared runtime code starts here when needed"],
];

const readme = (
  <>
    <Center>
      <Heading level={1}>{PROJECT.name}</Heading>

      <Paragraph>
        <Bold>{PROJECT.oneLine}</Bold>
      </Paragraph>

      <Paragraph>{PROJECT.tagline}</Paragraph>

      <Badges>
        <Badge label="shape" value="mise + BATS" color="4EAA25" logo="gnubash" logoColor="white" />
        <Badge label="tests" value={`${testCount}`} color="brightgreen" href="test/" />
        <Badge label="lints" value={`${lints.length}`} color="blue" />
        <Badge label="README" value="TSX" color="f472b6" />
        <Badge label="License" value={PROJECT.license} color="blue" href="LICENSE" />
      </Badges>
    </Center>

    <LineBreak />

    <Section title="What this is">
      <Paragraph>
        <Code>template</Code>
        {" is the default empty room for a new KnickKnackLabs tool: mise-managed tasks, BATS tests, codebase convention lints, generated README, CI, and a "}
        <Code>doctor</Code>
        {" task that tells you whether your clone has the optional local pre-commit hook installed."}
      </Paragraph>

      <Paragraph>
        {"This is deliberately a normal repo, not a GitHub template repo. Copy the files, start fresh history for the new tool, and keep this repo as the living reference skeleton."}
      </Paragraph>

      <Paragraph>
        {"It intentionally does "}
        <Bold>not</Bold>
        {" decide what your product does. Copy it, rename the obvious constants, then add the first real command only when the workflow is clear."}
      </Paragraph>
    </Section>

    <Section title="Quick start">
      <CodeBlock lang="bash">{`gh repo clone KnickKnackLabs/template my-tool
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
gh repo create KnickKnackLabs/my-tool --public --source=. --remote=origin --push`}</CodeBlock>
    </Section>

    <Section title="Goodies baked in">
      <Table>
        <TableHead>
          <Cell>Goodie</Cell>
          <Cell>Why it exists</Cell>
          <Cell>Where</Cell>
        </TableHead>
        <TableRow>
          <Cell>Generated README</Cell>
          <Cell>TSX can count tests, list tasks, and keep docs honest in CI.</Cell>
          <Cell><Code>README.tsx</Code></Cell>
        </TableRow>
        <TableRow>
          <Cell>Doctor hook check</Cell>
          <Cell>Local pre-commit hooks are clone-local, so the repo can report them without pretending they are tracked.</Cell>
          <Cell><Code>mise run doctor</Code></Cell>
        </TableRow>
        <TableRow>
          <Cell>Convention lints</Cell>
          <Cell>Best-practice drift gets caught as code, not folklore.</Cell>
          <Cell><Code>[_.codebase].lint</Code></Cell>
        </TableRow>
        <TableRow>
          <Cell>Real test path</Cell>
          <Cell>BATS tests call tasks through <Code>mise run</Code>, not raw scripts.</Cell>
          <Cell><Code>test/test_helper.bash</Code></Cell>
        </TableRow>
        <TableRow>
          <Cell>Mac + Linux CI</Cell>
          <Cell>Bash and tooling differences show up before merge.</Cell>
          <Cell>{oses.join(" + ") || "workflow pending"}</Cell>
        </TableRow>
      </Table>
    </Section>

    <Section title="Scaffold inventory">
      <Table>
        <TableHead>
          <Cell>Path</Cell>
          <Cell>Status</Cell>
          <Cell>Purpose</Cell>
        </TableHead>
        {scaffold.map(([path, purpose]) => (
          <TableRow>
            <Cell><Code>{path}</Code></Cell>
            <Cell>{status(path)}</Cell>
            <Cell>{purpose}</Cell>
          </TableRow>
        ))}
      </Table>
    </Section>

    <Section title="Tasks">
      <Table>
        <TableHead>
          <Cell>Task</Cell>
          <Cell>Description</Cell>
        </TableHead>
        {tasks.map((task) => (
          <TableRow>
            <Cell><Code>{`mise run ${task.name}`}</Code></Cell>
            <Cell>{task.description}</Cell>
          </TableRow>
        ))}
      </Table>
    </Section>

    <Section title="When you copy it">
      <List ordered>
        <Item>Rename <Code>PROJECT</Code> in <Code>README.tsx</Code>.</Item>
        <Item>Rewrite this README around the actual tool, but keep the dynamic counters if they help.</Item>
        <Item>Replace <Code>CONTRIBUTING.md</Code> with repo-specific orientation.</Item>
        <Item>Add real task files under <Code>.mise/tasks/</Code>; use <Code>$MISE_CONFIG_ROOT</Code> inside tasks only.</Item>
        <Item>Put shared Bash helpers in <Code>lib/</Code> only once multiple tasks need them.</Item>
        <Item>If the installed tool resolves caller-relative paths, read the shiv-provided <Code>{"<PACKAGE>_CALLER_PWD"}</Code> variable, not generic <Code>CALLER_PWD</Code>.</Item>
      </List>
    </Section>

    <Details summary="Current convention checks">
      <Paragraph>
        {"This template currently asks "}
        <Link href="https://github.com/KnickKnackLabs/codebase">codebase</Link>
        {" to run these lint rules:"}
      </Paragraph>
      <CodeBlock>{lints.join("\n")}</CodeBlock>
    </Details>

    <Section title="Validation">
      <CodeBlock lang="bash">{`mise run test
codebase lint "$PWD"
readme build --check
git diff --check`}</CodeBlock>

      <Paragraph>
        {"The starter suite currently has "}
        <Bold>{`${testCount} tests`}</Bold>
        {" and "}
        <Bold>{`${tasks.length} public tasks`}</Bold>
        {". Those numbers are read from the repo at README build time."}
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
        {"A skeleton is a kindness to whoever has to remember the boring parts tomorrow."}
      </Sub>
    </Center>
  </>
);

console.log(readme);
