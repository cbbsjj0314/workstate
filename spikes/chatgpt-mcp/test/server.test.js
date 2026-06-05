import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, it } from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import {
  EVENT_LOG_ENV,
  FORBIDDEN_PERSISTED_FIELDS,
  SafeToolError,
  WorkStateProbeStorage,
  defaultEventLogPath,
} from "../lib/storage.js";
import {
  MARKER,
  SERVER_NAME,
  createHttpHandler,
  createProbeMcpServer,
  limits,
  startServer,
} from "../server.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function makeTempRepo() {
  const dir = await fs.mkdtemp(path.join(tmpdir(), "workstate-chatgpt-mcp-test-"));
  await fs.mkdir(path.join(dir, "repo"));
  return {
    root: dir,
    repoRoot: path.join(dir, "repo"),
    logPath: path.join(dir, "events", "probe.jsonl"),
  };
}

async function readJsonl(logPath) {
  const text = await fs.readFile(logPath, "utf8");
  return text
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function validInput(overrides = {}) {
  return {
    probe_id: "probe_alpha",
    scenario: "direct",
    marker: MARKER,
    ...overrides,
  };
}

async function withClient(storage, fn) {
  const handler = createHttpHandler({ storage, allowedOrigins: [] });
  const server = await startServer({ host: "127.0.0.1", port: 0, handler });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : undefined;
  const client = new Client({ name: "workstate-test-client", version: "0.1.0" });
  const transport = new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`));

  try {
    await client.connect(transport);
    return await fn(client);
  } finally {
    await client.close().catch(() => undefined);
    await new Promise((resolve) => server.close(resolve));
  }
}

describe("storage path resolution", () => {
  it("uses XDG_DATA_HOME for default event log path", () => {
    const resolved = defaultEventLogPath({ XDG_DATA_HOME: "/tmp/workstate-data", HOME: "/tmp/home" });
    assert.equal(resolved, path.join("/tmp/workstate-data", "workstate", "events", "chatgpt-mcp-probe.jsonl"));
  });

  it("uses WORKSTATE_CHATGPT_MCP_EVENT_LOG override", () => {
    const resolved = defaultEventLogPath({
      [EVENT_LOG_ENV]: "/tmp/custom/probe.jsonl",
      XDG_DATA_HOME: "/tmp/workstate-data",
    });
    assert.equal(resolved, "/tmp/custom/probe.jsonl");
  });

  it("refuses to write inside the repository", async () => {
    const temp = await makeTempRepo();
    assert.throws(
      () =>
        new WorkStateProbeStorage({
          repoRoot: temp.repoRoot,
          logPath: path.join(temp.repoRoot, "events.jsonl"),
        }),
      SafeToolError,
    );
  });
});

describe("record_observation idempotency and JSONL normalization", () => {
  it("appends one normalized JSONL line for a first valid call", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      now: () => "2026-06-05T20:00:00.000Z",
      newRecordId: () => "rec_00000000-0000-4000-8000-000000000001",
    });

    const result = await storage.recordObservation(validInput());
    assert.equal(result.duplicate, false);
    assert.equal(result.attempt_count, 1);

    const records = await readJsonl(temp.logPath);
    assert.equal(records.length, 1);
    assert.deepEqual(records[0], {
      schema_version: 1,
      recorded_at: "2026-06-05T20:00:00.000Z",
      source: "chatgpt-mcp-probe",
      tool_name: "record_observation",
      record_id: "rec_00000000-0000-4000-8000-000000000001",
      probe_id: "probe_alpha",
      scenario: "direct",
      marker: MARKER,
    });

    const persisted = JSON.stringify(records[0]);
    for (const forbidden of FORBIDDEN_PERSISTED_FIELDS) {
      assert.equal(persisted.includes(forbidden), false, forbidden);
    }
  });

  it("concurrent identical calls append exactly one line and return shared record_id with distinct ordinals", async () => {
    const temp = await makeTempRepo();
    const entered = deferred();
    const release = deferred();
    let appendCalls = 0;

    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      appendRecord: async (record) => {
        appendCalls += 1;
        entered.resolve();
        await release.promise;
        await fs.mkdir(path.dirname(temp.logPath), { recursive: true });
        await fs.appendFile(temp.logPath, `${JSON.stringify(record)}\n`, "utf8");
      },
    });

    const first = storage.recordObservation(validInput());
    await entered.promise;
    const retry = storage.recordObservation(validInput());
    release.resolve();

    const results = await Promise.all([first, retry]);
    const attempts = new Set(results.map((result) => result.attempt_count));

    assert.equal(appendCalls, 1);
    assert.equal(results[0].record_id, results[1].record_id);
    assert.deepEqual(attempts, new Set([1, 2]));
    assert.equal(results.filter((result) => result.duplicate === false).length, 1);
    assert.equal(results.filter((result) => result.duplicate === true).length, 1);

    const records = await readJsonl(temp.logPath);
    assert.equal(records.length, 1);
  });

  it("rejects a concurrent conflicting call for the same probe_id", async () => {
    const temp = await makeTempRepo();
    const entered = deferred();
    const release = deferred();
    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      appendRecord: async (record) => {
        entered.resolve();
        await release.promise;
        await fs.mkdir(path.dirname(temp.logPath), { recursive: true });
        await fs.appendFile(temp.logPath, `${JSON.stringify(record)}\n`, "utf8");
      },
    });

    const first = storage.recordObservation(validInput());
    await entered.promise;
    await assert.rejects(
      storage.recordObservation(validInput({ scenario: "indirect" })),
      /probe_id was reused with different input/,
    );
    release.resolve();
    await first;
  });

  it("does not let concurrent unique writes exceed the process write limit", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      maxWritesPerProcess: 1,
    });

    const results = await Promise.allSettled([
      storage.recordObservation(validInput({ probe_id: "probe_one" })),
      storage.recordObservation(validInput({ probe_id: "probe_two" })),
    ]);

    assert.equal(results.filter((result) => result.status === "fulfilled").length, 1);
    assert.equal(results.filter((result) => result.status === "rejected").length, 1);
    const records = await readJsonl(temp.logPath);
    assert.equal(records.length, 1);
  });

  it("failed append clears pending idempotency state and allows a later retry to succeed", async () => {
    const temp = await makeTempRepo();
    const entered = deferred();
    const release = deferred();
    let shouldFail = true;
    let ids = 0;
    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      newRecordId: () => {
        ids += 1;
        return ids === 1
          ? "rec_00000000-0000-4000-8000-000000000001"
          : "rec_00000000-0000-4000-8000-000000000002";
      },
      appendRecord: async (record) => {
        entered.resolve();
        await release.promise;
        if (shouldFail) {
          throw new Error("disk failed");
        }
        await fs.mkdir(path.dirname(temp.logPath), { recursive: true });
        await fs.appendFile(temp.logPath, `${JSON.stringify(record)}\n`, "utf8");
      },
    });

    const owner = storage.recordObservation(validInput());
    await entered.promise;
    const waiter = storage.recordObservation(validInput());
    release.resolve();

    await assert.rejects(owner, /observation was not recorded/);
    await assert.rejects(waiter, /observation was not recorded/);

    shouldFail = false;
    const retry = await storage.recordObservation(validInput());
    assert.equal(retry.duplicate, false);
    assert.equal(retry.attempt_count, 1);
    assert.equal(retry.record_id, "rec_00000000-0000-4000-8000-000000000002");

    const records = await readJsonl(temp.logPath);
    assert.equal(records.length, 1);
  });

  it("refuses additional writes when the event log file size limit would be exceeded", async () => {
    const temp = await makeTempRepo();
    await fs.mkdir(path.dirname(temp.logPath), { recursive: true });
    await fs.writeFile(temp.logPath, "x".repeat(100), "utf8");
    const storage = new WorkStateProbeStorage({
      repoRoot: temp.repoRoot,
      logPath: temp.logPath,
      maxEventLogBytes: 101,
    });

    await assert.rejects(storage.recordObservation(validInput()), /event log size limit exceeded/);
  });
});

describe("MCP descriptors and tool results", () => {
  it("lists exactly two tools with annotations and schemas", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({ repoRoot: temp.repoRoot, logPath: temp.logPath });

    await withClient(storage, async (client) => {
      const result = await client.listTools();
      assert.deepEqual(
        result.tools.map((tool) => tool.name).sort(),
        ["health_check", "record_observation"],
      );

      const health = result.tools.find((tool) => tool.name === "health_check");
      const write = result.tools.find((tool) => tool.name === "record_observation");
      assert.deepEqual(health.annotations, {
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
      });
      assert.deepEqual(write.annotations, {
        readOnlyHint: false,
        destructiveHint: false,
        openWorldHint: false,
      });
      assert.equal(Boolean(health.inputSchema), true);
      assert.equal(Boolean(health.outputSchema), true);
      assert.equal(Boolean(write.inputSchema), true);
      assert.equal(Boolean(write.outputSchema), true);
    });
  });

  it("returns structuredContent and safe JSON content for health_check", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({ repoRoot: temp.repoRoot, logPath: temp.logPath });

    await withClient(storage, async (client) => {
      const result = await client.callTool({ name: "health_check", arguments: {} });
      assert.equal(result.structuredContent.ok, true);
      assert.equal(result.structuredContent.server_name, SERVER_NAME);
      assert.deepEqual(JSON.parse(result.content[0].text), result.structuredContent);
      const payload = JSON.stringify(result);
      assert.equal(payload.includes(temp.repoRoot), false);
      assert.equal(payload.includes(process.env.HOME ?? "__no_home__"), false);
    });
  });

  it("returns structuredContent and safe JSON content for record_observation", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({ repoRoot: temp.repoRoot, logPath: temp.logPath });

    await withClient(storage, async (client) => {
      const result = await client.callTool({
        name: "record_observation",
        arguments: validInput(),
      });
      assert.equal(result.structuredContent.accepted, true);
      assert.equal(result.structuredContent.duplicate, false);
      assert.equal(result.structuredContent.attempt_count, 1);
      assert.deepEqual(JSON.parse(result.content[0].text), result.structuredContent);
    });
  });

  it("rejects arbitrary or oversized tool input before handler side effects", async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({ repoRoot: temp.repoRoot, logPath: temp.logPath });

    await withClient(storage, async (client) => {
      const result = await client.callTool({
        name: "record_observation",
        arguments: {
          probe_id: `probe_${"a".repeat(100)}`,
          scenario: "direct",
          marker: MARKER,
          note: "raw prompt text should not be accepted",
        },
      });
      assert.equal(result.isError, true);
      await assert.rejects(fs.stat(temp.logPath), /ENOENT/);
    });
  });
});

describe("HTTP bounded-exposure behavior", () => {
  let server;
  let baseUrl;

  beforeEach(async () => {
    const temp = await makeTempRepo();
    const storage = new WorkStateProbeStorage({ repoRoot: temp.repoRoot, logPath: temp.logPath });
    const handler = createHttpHandler({ storage, allowedOrigins: [], maxBodyBytes: 8 });
    server = await startServer({ host: "127.0.0.1", port: 0, handler });
    const address = server.address();
    const port = typeof address === "object" && address ? address.port : undefined;
    baseUrl = `http://127.0.0.1:${port}`;
  });

  afterEach(async () => {
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it("sets request and headers timeouts", () => {
    assert.equal(server.requestTimeout, limits.requestTimeoutMs);
    assert.equal(server.headersTimeout, limits.headersTimeoutMs);
  });

  it("returns human-readable health only at GET /", async () => {
    const response = await fetch(`${baseUrl}/`);
    assert.equal(response.status, 200);
    assert.equal(await response.text(), `${SERVER_NAME} ok\n`);
  });

  it("rejects unsupported methods safely", async () => {
    const response = await fetch(`${baseUrl}/mcp`, { method: "PUT" });
    assert.equal(response.status, 405);
    const text = await response.text();
    assert.equal(text.includes("Error:"), false);
  });

  it("rejects unsupported content type safely", async () => {
    const response = await fetch(`${baseUrl}/mcp`, {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: "{}",
    });
    assert.equal(response.status, 415);
  });

  it("rejects oversized request body safely", async () => {
    const response = await new Promise((resolve, reject) => {
      const request = http.request(
        `${baseUrl}/mcp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        },
        resolve,
      );
      request.on("error", reject);
      request.write(JSON.stringify({ long: "x".repeat(100) }));
      request.end();
    });
    assert.equal(response.statusCode, 413);
  });
});
