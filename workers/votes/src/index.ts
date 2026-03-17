export interface Env {
  DB: D1Database;
  ACTOR_SALT?: string;
  THROTTLE_SECONDS?: string;
  CORS_ORIGIN?: string;
  LOG_LEVEL?: string;
}

type VoteAction = "like" | "dislike";

type VoteBody = {
  entityType?: string;
  entityId?: string;
  action?: VoteAction;
};

type VoteCounts = {
  likeCount: number;
  dislikeCount: number;
};

type LogLevel = "debug" | "info" | "warn" | "error";

type RequestContext = {
  requestId: string;
  method: string;
  path: string;
};

const ENTITY_TYPE_RE = /^[a-z0-9_-]{1,32}$/i;
const ENTITY_ID_RE = /^[a-z0-9._:-]{1,128}$/i;
const DEFAULT_THROTTLE_SECONDS = 8;
const LOG_LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

function corsHeaders(env: Env): HeadersInit {
  return {
    "Access-Control-Allow-Origin": env.CORS_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(
  env: Env,
  payload: unknown,
  status = 200,
  extraHeaders: HeadersInit = {},
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...corsHeaders(env),
      ...extraHeaders,
    },
  });
}

function error(
  env: Env,
  status: number,
  code: string,
  message: string,
  extra: Record<string, unknown> = {},
): Response {
  return json(
    env,
    {
      ok: false,
      error: {
        code,
        message,
        ...extra,
      },
    },
    status,
  );
}

function ok(env: Env, data: unknown): Response {
  return json(env, { ok: true, data }, 200);
}

function normalizedPath(request: Request): string {
  const pathname = new URL(request.url).pathname.replace(/\/+$/, "") || "/";
  if (pathname === "/api") return "/";
  if (pathname.startsWith("/api/")) return pathname.slice(4) || "/";
  return pathname;
}

function normalizeEntityType(value: string): string | null {
  const v = value.trim().toLowerCase();
  if (!ENTITY_TYPE_RE.test(v)) return null;
  return v;
}

function normalizeEntityId(value: string): string | null {
  const v = value.trim();
  if (!ENTITY_ID_RE.test(v)) return null;
  return v;
}

function parseThrottleSeconds(raw: string | undefined): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_THROTTLE_SECONDS;
  }
  return Math.floor(parsed);
}

function parseLogLevel(raw: string | undefined): LogLevel {
  const v = String(raw ?? "")
    .trim()
    .toLowerCase();
  if (v === "debug" || v === "info" || v === "warn" || v === "error") {
    return v;
  }
  return "warn";
}

function shouldLog(env: Env, level: LogLevel): boolean {
  const activeLevel = parseLogLevel(env.LOG_LEVEL);
  return LOG_LEVEL_ORDER[level] >= LOG_LEVEL_ORDER[activeLevel];
}

function log(env: Env, level: LogLevel, event: string, data: Record<string, unknown> = {}): void {
  try {
    if (!shouldLog(env, level)) return;
    const payload = {
      ts: new Date().toISOString(),
      level,
      event,
      ...data,
    };
    const msg = JSON.stringify(payload);
    if (level === "error") {
      console.error(msg);
      return;
    }
    if (level === "warn") {
      console.warn(msg);
      return;
    }
    console.log(msg);
  } catch {
    // Never let logging errors break request handling.
  }
}

function getClientIp(request: Request): string {
  const cfIp = request.headers.get("CF-Connecting-IP");
  if (cfIp) return cfIp.trim();

  const forwardedFor = request.headers.get("X-Forwarded-For");
  if (forwardedFor) {
    const first = forwardedFor.split(",")[0]?.trim();
    if (first) return first;
  }

  return "0.0.0.0";
}

function createRequestId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }
}

async function sha256Hex(input: string): Promise<string> {
  const encoded = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  const bytes = new Uint8Array(digest);
  return Array.from(bytes)
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
}

async function buildActorHash(request: Request, env: Env): Promise<string> {
  const ip = getClientIp(request);
  const ua = request.headers.get("User-Agent") || "unknown";
  const lang = request.headers.get("Accept-Language") || "unknown";
  const salt = env.ACTOR_SALT?.trim() || "change-me-in-production";
  return sha256Hex(`${salt}|${ip}|${ua}|${lang}`);
}

async function readJsonBody(request: Request): Promise<VoteBody | null> {
  try {
    return (await request.json()) as VoteBody;
  } catch {
    return null;
  }
}

async function fetchCounts(env: Env, entityType: string, entityId: string): Promise<VoteCounts> {
  const row = await env.DB.prepare(
    `SELECT like_count, dislike_count
       FROM vote_counters
      WHERE entity_type = ?1 AND entity_id = ?2
      LIMIT 1`,
  )
    .bind(entityType, entityId)
    .first<{ like_count?: number; dislike_count?: number }>();

  return {
    likeCount: row?.like_count ?? 0,
    dislikeCount: row?.dislike_count ?? 0,
  };
}

async function handleGetVotes(request: Request, env: Env, ctx: RequestContext): Promise<Response> {
  const url = new URL(request.url);
  const rawType = url.searchParams.get("entityType") || "";
  const rawId = url.searchParams.get("entityId") || "";

  const entityType = normalizeEntityType(rawType);
  const entityId = normalizeEntityId(rawId);

  if (!entityType || !entityId) {
    log(env, "warn", "votes.get.invalid_target", {
      requestId: ctx.requestId,
      method: ctx.method,
      path: ctx.path,
      rawType,
      rawId,
    });
    return error(env, 400, "INVALID_TARGET", "entityType or entityId is invalid");
  }

  const counts = await fetchCounts(env, entityType, entityId);
  log(env, "debug", "votes.get.success", {
    requestId: ctx.requestId,
    path: ctx.path,
    entityType,
    entityId,
    likeCount: counts.likeCount,
    dislikeCount: counts.dislikeCount,
  });
  return ok(env, {
    entityType,
    entityId,
    ...counts,
  });
}

async function handlePostVotes(request: Request, env: Env, ctx: RequestContext): Promise<Response> {
  const body = await readJsonBody(request);
  if (!body) {
    log(env, "warn", "votes.post.invalid_json", {
      requestId: ctx.requestId,
      method: ctx.method,
      path: ctx.path,
    });
    return error(env, 400, "INVALID_JSON", "body must be valid JSON");
  }

  const entityType = normalizeEntityType(body.entityType || "");
  const entityId = normalizeEntityId(body.entityId || "");
  const action = body.action;

  if (!entityType || !entityId) {
    log(env, "warn", "votes.post.invalid_target", {
      requestId: ctx.requestId,
      method: ctx.method,
      path: ctx.path,
      rawEntityType: body.entityType ?? null,
      rawEntityId: body.entityId ?? null,
    });
    return error(env, 400, "INVALID_TARGET", "entityType or entityId is invalid");
  }

  if (action !== "like" && action !== "dislike") {
    log(env, "warn", "votes.post.invalid_action", {
      requestId: ctx.requestId,
      method: ctx.method,
      path: ctx.path,
      entityType,
      entityId,
      rawAction: action ?? null,
    });
    return error(env, 400, "INVALID_ACTION", "action must be like or dislike");
  }

  const actorHash = await buildActorHash(request, env);
  const nowSeconds = Math.floor(Date.now() / 1000);
  const throttleSeconds = parseThrottleSeconds(env.THROTTLE_SECONDS);

  const latest = await env.DB.prepare(
    `SELECT created_at
       FROM vote_events
      WHERE actor_hash = ?1
        AND entity_type = ?2
        AND entity_id = ?3
        AND action = ?4
      ORDER BY created_at DESC
      LIMIT 1`,
  )
    .bind(actorHash, entityType, entityId, action)
    .first<{ created_at?: number }>();

  const latestAt = latest?.created_at ?? 0;
  const elapsed = nowSeconds - latestAt;
  if (latestAt > 0 && elapsed < throttleSeconds) {
    const retryAfterSeconds = Math.max(1, throttleSeconds - elapsed);
    log(env, "warn", "votes.post.rate_limited", {
      requestId: ctx.requestId,
      method: ctx.method,
      path: ctx.path,
      entityType,
      entityId,
      action,
      retryAfterSeconds,
      actorHashPrefix: actorHash.slice(0, 8),
    });
    return error(env, 429, "RATE_LIMITED", "vote throttled", {
      retryAfterSeconds,
    });
  }

  const insertEvent = env.DB.prepare(
    `INSERT INTO vote_events (
       entity_type,
       entity_id,
       action,
       actor_hash,
       created_at
     ) VALUES (?1, ?2, ?3, ?4, ?5)`,
  ).bind(entityType, entityId, action, actorHash, nowSeconds);

  const upsertCounter = env.DB.prepare(
    `INSERT INTO vote_counters (
       entity_type,
       entity_id,
       like_count,
       dislike_count,
       updated_at
     ) VALUES (
       ?1,
       ?2,
       CASE WHEN ?3 = 'like' THEN 1 ELSE 0 END,
       CASE WHEN ?3 = 'dislike' THEN 1 ELSE 0 END,
       ?4
     )
     ON CONFLICT(entity_type, entity_id) DO UPDATE SET
       like_count = vote_counters.like_count + CASE WHEN excluded.like_count > 0 THEN 1 ELSE 0 END,
       dislike_count = vote_counters.dislike_count + CASE WHEN excluded.dislike_count > 0 THEN 1 ELSE 0 END,
       updated_at = excluded.updated_at`,
  ).bind(entityType, entityId, action, nowSeconds);

  await env.DB.batch([insertEvent, upsertCounter]);

  const counts = await fetchCounts(env, entityType, entityId);
  log(env, "debug", "votes.post.success", {
    requestId: ctx.requestId,
    path: ctx.path,
    entityType,
    entityId,
    action,
    likeCount: counts.likeCount,
    dislikeCount: counts.dislikeCount,
    actorHashPrefix: actorHash.slice(0, 8),
  });
  return ok(env, {
    entityType,
    entityId,
    ...counts,
  });
}

async function handleRequest(request: Request, env: Env): Promise<Response> {
    const startedAt = Date.now();
    const requestId = createRequestId();
    const method = request.method;
    let path = "/";
    let rawPath = "/";

    try {
      rawPath = new URL(request.url).pathname;
      path = normalizedPath(request);
      const cfRay = request.headers.get("cf-ray");

      log(env, "debug", "request.start", {
        requestId,
        method,
        rawPath,
        path,
        cfRay,
      });

      let response: Response;

      if (request.method === "OPTIONS") {
        response = new Response(null, {
          status: 204,
          headers: corsHeaders(env),
        });
      } else {
        const ctx: RequestContext = { requestId, method, path };

        if (path === "/votes" && request.method === "GET") {
          response = await handleGetVotes(request, env, ctx);
        } else if (path === "/votes" && request.method === "POST") {
          response = await handlePostVotes(request, env, ctx);
        } else {
          log(env, "warn", "request.route_not_found", {
            requestId,
            method,
            rawPath,
            path,
          });
          response = error(env, 404, "NOT_FOUND", "route not found");
        }
      }

      const durationMs = Date.now() - startedAt;
      log(env, "debug", "request.end", {
        requestId,
        method,
        rawPath,
        path,
        status: response.status,
        durationMs,
      });

      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const stack = err instanceof Error ? err.stack : undefined;
      log(env, "error", "request.unhandled_error", {
        requestId,
        method,
        rawPath,
        path,
        message,
        stack,
      });
      return error(env, 500, "INTERNAL_ERROR", "internal server error");
    }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return Promise.resolve(handleRequest(request, env));
  },
};
