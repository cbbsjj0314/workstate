import { randomUUID } from "node:crypto";
import http from "node:http";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod/v4";
import {
  DEFAULT_MAX_EVENT_LOG_BYTES,
  DEFAULT_MAX_WRITES_PER_PROCESS,
  SafeToolError,
  WorkStateProbeStorage,
  jsonToolResult,
  safeToolErrorResult,
} from "./lib/storage.js";

export const SERVER_NAME = "workstate-chatgpt-mcp-capability-probe";
export const SERVER_VERSION = "0.1.0";
export const DEFAULT_HOST = "127.0.0.1";
export const DEFAULT_PORT = 2091;
export const MAX_HTTP_BODY_BYTES = 16 * 1024;
export const REQUEST_TIMEOUT_MS = 10_000;
export const HEADERS_TIMEOUT_MS = 5_000;
export const MARKER = "workstate_chatgpt_mcp_probe_v1";

const HEALTH_INPUT_SCHEMA = z.object({}).strict();
const HEALTH_OUTPUT_SCHEMA = z
  .object({
    ok: z.literal(true),
    server_name: z.literal(SERVER_NAME),
    schema_version: z.literal(1),
    response_id: z.string().regex(/^resp_[0-9a-f-]{36}$/),
    responded_at: z.string().datetime(),
  })
  .strict();

const RECORD_INPUT_SCHEMA = z
  .object({
    probe_id: z
      .string()
      .regex(/^probe_[a-z0-9][a-z0-9_-]{0,30}$/)
      .max(37),
    scenario: z.enum(["direct", "indirect"]),
    marker: z.literal(MARKER),
  })
  .strict();

const RECORD_OUTPUT_SCHEMA = z
  .object({
    accepted: z.literal(true),
    record_id: z.string().regex(/^rec_[0-9a-f-]{36}$/),
    probe_id: z.string(),
    scenario: z.enum(["direct", "indirect"]),
    recorded_at: z.string().datetime(),
    duplicate: z.boolean(),
    attempt_count: z.number().int().min(1),
  })
  .strict();

export function createProbeMcpServer(options = {}) {
  const storage = options.storage ?? new WorkStateProbeStorage(options.storageOptions);
  const now = options.now ?? (() => new Date().toISOString());
  const newResponseId = options.newResponseId ?? (() => `resp_${randomUUID()}`);

  const server = new McpServer(
    {
      name: SERVER_NAME,
      version: SERVER_VERSION,
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  server.registerTool(
    "health_check",
    {
      title: "Health Check",
      description: "Return a safe synthetic health response for this probe server.",
      inputSchema: HEALTH_INPUT_SCHEMA,
      outputSchema: HEALTH_OUTPUT_SCHEMA,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
      },
    },
    async () => {
      const structuredContent = {
        ok: true,
        server_name: SERVER_NAME,
        schema_version: 1,
        response_id: newResponseId(),
        responded_at: now(),
      };
      return jsonToolResult(structuredContent);
    },
  );

  server.registerTool(
    "record_observation",
    {
      title: "Record Synthetic Observation",
      description: "Append one bounded synthetic observation for ChatGPT MCP write capability probing.",
      inputSchema: RECORD_INPUT_SCHEMA,
      outputSchema: RECORD_OUTPUT_SCHEMA,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        openWorldHint: false,
      },
    },
    async (input) => {
      try {
        const structuredContent = await storage.recordObservation(input);
        return jsonToolResult(structuredContent);
      } catch (error) {
        if (error instanceof SafeToolError) {
          return safeToolErrorResult(error.message);
        }
        return safeToolErrorResult();
      }
    },
  );

  return { server, storage };
}

export function allowedOriginsFromEnv(env = process.env) {
  if (!env.WORKSTATE_CHATGPT_MCP_ALLOWED_ORIGINS) {
    return ["https://chatgpt.com", "https://chat.openai.com"];
  }

  return env.WORKSTATE_CHATGPT_MCP_ALLOWED_ORIGINS.split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

export function applyCors(req, res, allowedOrigins) {
  const origin = req.headers.origin;
  if (!origin || !allowedOrigins.includes(origin)) {
    return;
  }

  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, mcp-session-id, Last-Event-ID, mcp-protocol-version");
  res.setHeader("Access-Control-Expose-Headers", "mcp-session-id");
}

function writeJson(res, statusCode, body, extraHeaders = {}) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(JSON.stringify(body));
}

function writeText(res, statusCode, text, extraHeaders = {}) {
  res.writeHead(statusCode, {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(text);
}

function methodNotAllowed(res, allow) {
  writeJson(
    res,
    405,
    {
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Method not allowed.",
      },
      id: null,
    },
    { Allow: allow },
  );
}

function unsupportedMediaType(res) {
  writeJson(res, 415, {
    jsonrpc: "2.0",
    error: {
      code: -32000,
      message: "Unsupported Media Type: Content-Type must be application/json.",
    },
    id: null,
  });
}

function payloadTooLarge(res) {
  writeJson(res, 413, {
    jsonrpc: "2.0",
    error: {
      code: -32000,
      message: "Request body too large.",
    },
    id: null,
  });
}

function badRequest(res) {
  writeJson(res, 400, {
    jsonrpc: "2.0",
    error: {
      code: -32700,
      message: "Malformed JSON request.",
    },
    id: null,
  });
}

function internalError(res) {
  writeJson(res, 500, {
    jsonrpc: "2.0",
    error: {
      code: -32603,
      message: "Internal server error.",
    },
    id: null,
  });
}

function hasJsonContentType(req) {
  const contentType = req.headers["content-type"];
  return typeof contentType === "string" && contentType.toLowerCase().split(";")[0].trim() === "application/json";
}

export async function readJsonBody(req, res, maxBytes = MAX_HTTP_BODY_BYTES) {
  let total = 0;
  const chunks = [];
  let tooLarge = false;

  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) {
      tooLarge = true;
      continue;
    }

    if (!tooLarge) {
      chunks.push(chunk);
    }
  }

  if (tooLarge) {
    payloadTooLarge(res);
    return { ok: false };
  }

  try {
    const text = Buffer.concat(chunks).toString("utf8");
    return { ok: true, body: JSON.parse(text) };
  } catch {
    badRequest(res);
    return { ok: false };
  }
}

export function createHttpHandler(options = {}) {
  const storage = options.storage ?? new WorkStateProbeStorage(options.storageOptions);
  const allowedOrigins = options.allowedOrigins ?? allowedOriginsFromEnv(options.env ?? process.env);
  const maxBodyBytes = options.maxBodyBytes ?? MAX_HTTP_BODY_BYTES;
  const newServer = options.newServer ?? (() => createProbeMcpServer({ storage }).server);

  return async function handleRequest(req, res) {
    applyCors(req, res, allowedOrigins);

    if (req.url === "/") {
      if (req.method === "GET") {
        writeText(res, 200, `${SERVER_NAME} ok\n`);
        return;
      }

      methodNotAllowed(res, "GET");
      return;
    }

    if (req.url !== "/mcp") {
      writeJson(res, 404, { error: "not found" });
      return;
    }

    if (req.method === "OPTIONS") {
      writeText(res, 204, "", { Allow: "POST, GET, DELETE, OPTIONS" });
      return;
    }

    if (req.method === "GET" || req.method === "DELETE") {
      methodNotAllowed(res, "POST");
      return;
    }

    if (req.method !== "POST") {
      methodNotAllowed(res, "POST");
      return;
    }

    if (!hasJsonContentType(req)) {
      unsupportedMediaType(res);
      return;
    }

    const parsed = await readJsonBody(req, res, maxBodyBytes);
    if (!parsed.ok) {
      return;
    }

    const mcpServer = newServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });

    try {
      await mcpServer.connect(transport);
      await transport.handleRequest(req, res, parsed.body);
    } catch {
      if (!res.headersSent) {
        internalError(res);
      }
    } finally {
      await transport.close().catch(() => undefined);
      await mcpServer.close().catch(() => undefined);
    }
  };
}

export function startServer(options = {}) {
  const host = options.host ?? DEFAULT_HOST;
  if (host !== DEFAULT_HOST) {
    throw new Error(`server host must be ${DEFAULT_HOST}`);
  }

  const port = Number(options.port ?? process.env.PORT ?? DEFAULT_PORT);
  const handler = options.handler ?? createHttpHandler(options);
  const server = http.createServer(handler);
  server.requestTimeout = REQUEST_TIMEOUT_MS;
  server.headersTimeout = HEADERS_TIMEOUT_MS;

  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      server.off("error", reject);
      resolve(server);
    });
  });
}

async function main() {
  const server = await startServer();
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("server did not bind to a TCP address");
  }
  console.log(`${SERVER_NAME} listening on http://${address.address}:${address.port}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(() => {
    console.error("failed to start server");
    process.exit(1);
  });
}

export const limits = {
  maxHttpBodyBytes: MAX_HTTP_BODY_BYTES,
  maxWritesPerProcess: DEFAULT_MAX_WRITES_PER_PROCESS,
  maxEventLogBytes: DEFAULT_MAX_EVENT_LOG_BYTES,
  requestTimeoutMs: REQUEST_TIMEOUT_MS,
  headersTimeoutMs: HEADERS_TIMEOUT_MS,
};
