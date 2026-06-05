import { randomUUID } from "node:crypto";
import { constants, promises as fs } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

export const EVENT_LOG_ENV = "WORKSTATE_CHATGPT_MCP_EVENT_LOG";
export const DEFAULT_EVENT_LOG_RELATIVE_PATH = path.join(
  "workstate",
  "events",
  "chatgpt-mcp-probe.jsonl",
);
export const DEFAULT_MAX_WRITES_PER_PROCESS = 20;
export const DEFAULT_MAX_EVENT_LOG_BYTES = 1024 * 1024;

export const FORBIDDEN_PERSISTED_FIELDS = [
  "prompt",
  "assistant",
  "assistant_response",
  "conversation",
  "conversation_id",
  "transcript",
  "transcript_path",
  "headers",
  "cookie",
  "authorization",
  "command",
  "path",
  "url",
  "note",
  "source_code",
  "repository_contents",
];

export class SafeToolError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "SafeToolError";
    this.code = code;
  }
}

export function normalizeProbeInput(input) {
  return {
    probe_id: input.probe_id,
    scenario: input.scenario,
    marker: input.marker,
  };
}

export function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }

  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
    .join(",")}}`;
}

export function defaultEventLogPath(env = process.env) {
  if (env[EVENT_LOG_ENV]) {
    return path.resolve(env[EVENT_LOG_ENV]);
  }

  const dataHome = env.XDG_DATA_HOME ? path.resolve(env.XDG_DATA_HOME) : path.join(homedir(), ".local", "share");
  return path.join(dataHome, DEFAULT_EVENT_LOG_RELATIVE_PATH);
}

export function assertLogPathOutsideRepo(logPath, repoRoot) {
  const resolvedLogPath = path.resolve(logPath);
  const resolvedRepoRoot = path.resolve(repoRoot);
  const relative = path.relative(resolvedRepoRoot, resolvedLogPath);

  if (relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))) {
    throw new SafeToolError("log_path_inside_repository", "event log path is not allowed");
  }

  return resolvedLogPath;
}

export function safeToolErrorResult(message = "tool call failed") {
  return {
    isError: true,
    content: [
      {
        type: "text",
        text: JSON.stringify({ accepted: false, error: message }),
      },
    ],
  };
}

export function jsonToolResult(structuredContent) {
  return {
    structuredContent,
    content: [
      {
        type: "text",
        text: JSON.stringify(structuredContent),
      },
    ],
  };
}

export class WorkStateProbeStorage {
  constructor(options = {}) {
    this.repoRoot = path.resolve(options.repoRoot ?? path.join(import.meta.dirname, "..", "..", ".."));
    this.logPath = assertLogPathOutsideRepo(
      path.resolve(options.logPath ?? defaultEventLogPath(options.env ?? process.env)),
      this.repoRoot,
    );
    this.maxWritesPerProcess = options.maxWritesPerProcess ?? DEFAULT_MAX_WRITES_PER_PROCESS;
    this.maxEventLogBytes = options.maxEventLogBytes ?? DEFAULT_MAX_EVENT_LOG_BYTES;
    this.appendRecord = options.appendRecord ?? this.#appendRecordToFile.bind(this);
    this.now = options.now ?? (() => new Date().toISOString());
    this.newRecordId = options.newRecordId ?? (() => `rec_${randomUUID()}`);
    this.idempotency = new Map();
    this.acceptedWriteCount = 0;
    this.writeQueue = Promise.resolve();
  }

  async recordObservation(input) {
    const normalized = normalizeProbeInput(input);
    const normalizedKey = stableStringify(normalized);
    const existing = this.idempotency.get(normalized.probe_id);

    if (existing) {
      if (existing.normalizedKey !== normalizedKey) {
        throw new SafeToolError("idempotency_conflict", "probe_id was reused with different input");
      }

      const attemptCount = ++existing.attemptCount;
      try {
        const result = await existing.promise;
        return {
          accepted: true,
          record_id: result.record_id,
          probe_id: normalized.probe_id,
          scenario: normalized.scenario,
          recorded_at: result.recorded_at,
          duplicate: true,
          attempt_count: attemptCount,
        };
      } catch (error) {
        throw new SafeToolError("record_not_persisted", "observation was not recorded");
      }
    }

    const record = {
      schema_version: 1,
      recorded_at: this.now(),
      source: "chatgpt-mcp-probe",
      tool_name: "record_observation",
      record_id: this.newRecordId(),
      probe_id: normalized.probe_id,
      scenario: normalized.scenario,
      marker: normalized.marker,
    };

    const pending = {
      normalizedKey,
      attemptCount: 1,
      promise: null,
    };

    pending.promise = this.#serializeWrite(async () => {
      await this.#persistUniqueRecord(record);
      return {
        record_id: record.record_id,
        recorded_at: record.recorded_at,
      };
    });

    this.idempotency.set(normalized.probe_id, pending);

    try {
      const result = await pending.promise;
      this.idempotency.set(normalized.probe_id, {
        normalizedKey,
        attemptCount: pending.attemptCount,
        promise: Promise.resolve(result),
      });

      return {
        accepted: true,
        record_id: result.record_id,
        probe_id: normalized.probe_id,
        scenario: normalized.scenario,
        recorded_at: result.recorded_at,
        duplicate: false,
        attempt_count: 1,
      };
    } catch (error) {
      if (this.idempotency.get(normalized.probe_id) === pending) {
        this.idempotency.delete(normalized.probe_id);
      }
      throw error instanceof SafeToolError
        ? error
        : new SafeToolError("record_not_persisted", "observation was not recorded");
    }
  }

  #serializeWrite(task) {
    const run = this.writeQueue.then(task, task);
    this.writeQueue = run.catch(() => undefined);
    return run;
  }

  async #persistUniqueRecord(record) {
    if (this.acceptedWriteCount >= this.maxWritesPerProcess) {
      throw new SafeToolError("write_limit_exceeded", "write limit exceeded");
    }

    const size = await this.#currentLogSize();
    const line = `${JSON.stringify(record)}\n`;
    const lineSize = Buffer.byteLength(line, "utf8");
    if (size + lineSize > this.maxEventLogBytes) {
      throw new SafeToolError("event_log_too_large", "event log size limit exceeded");
    }

    await this.appendRecord(record);
    this.acceptedWriteCount += 1;
  }

  async #currentLogSize() {
    try {
      const stat = await fs.stat(this.logPath);
      if (!stat.isFile()) {
        throw new SafeToolError("event_log_not_file", "event log path is not allowed");
      }
      return stat.size;
    } catch (error) {
      if (error?.code === "ENOENT") {
        return 0;
      }
      if (error instanceof SafeToolError) {
        throw error;
      }
      throw new SafeToolError("event_log_unavailable", "event log is unavailable");
    }
  }

  async #appendRecordToFile(record) {
    const parent = path.dirname(this.logPath);
    await fs.mkdir(parent, { recursive: true, mode: 0o700 });

    const handle = await fs.open(this.logPath, constants.O_WRONLY | constants.O_CREAT | constants.O_APPEND, 0o600);
    try {
      await handle.writeFile(`${JSON.stringify(record)}\n`, { encoding: "utf8" });
    } finally {
      await handle.close();
    }

    await fs.chmod(parent, 0o700).catch(() => undefined);
    await fs.chmod(this.logPath, 0o600).catch(() => undefined);
  }
}
