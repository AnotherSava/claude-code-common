// Sign-in for an app that trusts a shared OpenID Connect sign-in service: the three /auth routes, the
// session cookie they issue, and the gate that asks for it.
//
// This file is installed unchanged by the `auth` skill from `~/.claude/skills/auth/module/signin.ts`.
// Change it there and re-install; an edit made in an app is lost at the next install and leaves that app
// running code the skill's end-to-end test never saw.
//
// Web-standard Request and Response only, with no Next.js import, so `proxy.ts`, a route handler and the
// skill's test harness all call the same functions. The syntax is erasable TypeScript, which lets Node run
// the file directly in that test.
//
// Environment: AUTH_ISSUER, AUTH_CLIENT_ID, AUTH_CLIENT_SECRET, AUTH_SESSION_SECRET and AUTH_ORIGIN, the
// app's own public origin. AUTH_DEV_USER, outside production only, signs every request in as that address
// without the sign-in service.

import { createHmac, timingSafeEqual } from "node:crypto";

import * as client from "openid-client";

export type Session = { sub: string; email: string; name: string };

const LOGIN_PATH = "/auth/login";
const CALLBACK_PATH = "/auth/callback";
const LOGOUT_PATH = "/auth/logout";

const SESSION_TTL_SECONDS = 30 * 24 * 60 * 60;
// How long a person has to finish signing in at the service before the app forgets it sent them there.
const FLOW_TTL_SECONDS = 10 * 60;

function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

function production(): boolean {
  return process.env.NODE_ENV === "production";
}

function origin(): string {
  return new URL(env("AUTH_ORIGIN")).origin;
}

// `__Host-` makes the browser refuse the cookie unless it is Secure, host-only and on Path=/, so a sibling
// subdomain cannot plant one for this app. It needs HTTPS, which only production has.
function cookieName(base: string): string {
  return production() ? `__Host-${base}` : base;
}

function cookie(name: string, value: string, maxAgeSeconds: number, path: string): string {
  return `${name}=${value}; Path=${path}; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSeconds}${production() ? "; Secure" : ""}`;
}

function setCookie(base: string, value: string, maxAgeSeconds: number): string {
  return cookie(cookieName(base), value, maxAgeSeconds, "/");
}

// The ID token the service issued, kept only to name the session to end at sign-out. Scoped to the logout
// path so no other request carries it, which is why it cannot take the `__Host-` prefix. It is the
// service's own signed token, handed back to the service and trusted by nothing here.
const ID_TOKEN_COOKIE = "auth_id_token";

function idTokenCookie(value: string, maxAgeSeconds: number): string {
  return cookie(ID_TOKEN_COOKIE, value, maxAgeSeconds, LOGOUT_PATH);
}

function readCookie(header: string | null, name: string): string | undefined {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index !== -1 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return undefined;
}

type Kind = "session" | "flow";

// The kind is part of what is signed, so a flow cookie can never be presented as a session.
function sign(kind: Kind, body: string): string {
  const secret = env("AUTH_SESSION_SECRET");
  if (secret.length < 32) throw new Error("AUTH_SESSION_SECRET is shorter than 32 characters");
  return createHmac("sha256", secret).update(`${kind}.${body}`).digest("base64url");
}

function seal(kind: Kind, payload: Record<string, string>, ttlSeconds: number, nowMs: number): string {
  const body = Buffer.from(JSON.stringify({ ...payload, exp: Math.floor(nowMs / 1000) + ttlSeconds })).toString("base64url");
  return `${body}.${sign(kind, body)}`;
}

// The signature is the security boundary: a payload is parsed only after it verifies.
function unseal(kind: Kind, token: string | undefined, nowMs: number): Record<string, unknown> | null {
  const parts = (token ?? "").split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) return null;
  const given = Buffer.from(parts[1]);
  const expected = Buffer.from(sign(kind, parts[0]));
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) return null;
  let payload: unknown;
  try {
    payload = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (typeof payload !== "object" || payload === null) return null;
  const record = payload as Record<string, unknown>;
  if (typeof record.exp !== "number" || record.exp * 1000 <= nowMs) return null;
  return record;
}

function devSession(): Session | null {
  const email = process.env.AUTH_DEV_USER;
  if (!email) return null;
  if (production()) throw new Error("AUTH_DEV_USER is set in production; remove it");
  return { sub: `dev:${email}`, email, name: email };
}

// Who the request is from, or null. Pass the request's Cookie header: `request.headers.get("cookie")` in
// proxy.ts and route handlers, `(await headers()).get("cookie")` in server components and actions.
//
// A session proves the sign-in service vouched for this person when the cookie was issued. What they may do
// in the app, and whether they still may, is the app's to decide on each request.
export function readSession(cookieHeader: string | null, nowMs: number = Date.now()): Session | null {
  const dev = devSession();
  if (dev) return dev;
  const record = unseal("session", readCookie(cookieHeader, cookieName("auth_session")), nowMs);
  if (!record || typeof record.sub !== "string" || typeof record.email !== "string" || typeof record.name !== "string") return null;
  return { sub: record.sub, email: record.email, name: record.name };
}

// A path on this site to return to after signing in, or null for anything else, so a crafted link cannot
// bounce a signed-in person to another origin. Protocol-relative (`//host`) and backslash forms (`/\host`,
// which browsers read as `//host`) are refused along with schemes and control characters. The `//` test
// runs again on the parsed path, because dot segments collapse there: `/.//host/x` and `/a/..//host/x`
// come out as `//host/x`, which `new URL(next, origin())` in login and callback reads as another host.
function safeNextPath(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(raw)) return null;
  let url: URL;
  try {
    url = new URL(raw, "http://signin.invalid");
  } catch {
    return null;
  }
  if (url.origin !== "http://signin.invalid" || url.pathname.startsWith("//") || url.pathname.startsWith("/auth/")) return null;
  return url.pathname + url.search;
}

function redirect(status: 302 | 303, location: string, cookies: string[] = []): Response {
  const headers = new Headers({ Location: location, "Cache-Control": "no-store" });
  for (const cookie of cookies) headers.append("Set-Cookie", cookie);
  return new Response(null, { status, headers });
}

function failure(status: number, message: string, cookies: string[] = []): Response {
  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
  for (const cookie of cookies) headers.append("Set-Cookie", cookie);
  return new Response(`<!doctype html><meta charset="utf-8"><title>Sign-in</title><p>${message}</p><p><a href="${LOGIN_PATH}">Try again</a></p>`, { status, headers });
}

// Call first thing in proxy.ts and return what it gives back when that is a Response. Everything needs a
// session unless it is a GET or HEAD of a path listed here; a write to a public path still needs one, since
// Next forwards a server action posted to any page. A string matches the whole path, a RegExp tests it.
//
// A page navigation without a session is sent to sign in and comes back where it was going. Anything else,
// a fetch or a form post, gets a 401 it can show, where a redirect would hand it a sign-in page as data.
//
// This is the outer check only. An action or a route handler that reads or changes data asks readSession
// itself, because a matcher in proxy.ts can exclude the path it runs on.
export function gate(request: Request, publicPaths: readonly (string | RegExp)[] = []): Response | null {
  const url = new URL(request.url);
  const path = url.pathname;
  if (path === LOGIN_PATH || path === CALLBACK_PATH || path === LOGOUT_PATH) return null;
  const read = request.method === "GET" || request.method === "HEAD";
  const isPublic = publicPaths.some((entry) => {
    if (typeof entry === "string") return entry === path;
    entry.lastIndex = 0;
    return entry.test(path);
  });
  if (read && isPublic) return null;
  if (readSession(request.headers.get("cookie"))) return null;
  const navigation = read && (request.headers.get("sec-fetch-dest") === "document" || (request.headers.get("accept") ?? "").includes("text/html"));
  if (!navigation) return new Response("Sign-in required", { status: 401, headers: { "Cache-Control": "no-store" } });
  return redirect(302, new URL(`${LOGIN_PATH}?next=${encodeURIComponent(path + url.search)}`, origin()).href);
}

let configuration: Promise<client.Configuration> | undefined;

function oidc(): Promise<client.Configuration> {
  if (!configuration) {
    const issuer = new URL(env("AUTH_ISSUER"));
    // Plain HTTP is accepted for a sign-in service on this machine and nowhere else.
    const local = issuer.protocol === "http:" && (issuer.hostname === "localhost" || issuer.hostname === "127.0.0.1");
    const pending = client.discovery(issuer, env("AUTH_CLIENT_ID"), undefined, client.ClientSecretBasic(env("AUTH_CLIENT_SECRET")), local ? { execute: [client.allowInsecureRequests] } : undefined);
    // A discovery that failed is asked again by the next request; one that worked is kept for the process.
    pending.catch(() => {
      if (configuration === pending) configuration = undefined;
    });
    configuration = pending;
  }
  return configuration;
}

// GET /auth/login?next=/path
export async function login(request: Request): Promise<Response> {
  const next = safeNextPath(new URL(request.url).searchParams.get("next")) ?? "/";
  if (readSession(request.headers.get("cookie"))) return redirect(302, new URL(next, origin()).href);
  const verifier = client.randomPKCECodeVerifier();
  const state = client.randomState();
  const nonce = client.randomNonce();
  const target = client.buildAuthorizationUrl(await oidc(), {
    redirect_uri: new URL(CALLBACK_PATH, origin()).href,
    scope: "openid profile email",
    state,
    nonce,
    code_challenge: await client.calculatePKCECodeChallenge(verifier),
    code_challenge_method: "S256",
  });
  return redirect(302, target.href, [setCookie("auth_flow", seal("flow", { state, nonce, verifier, next }, FLOW_TTL_SECONDS, Date.now()), FLOW_TTL_SECONDS)]);
}

// GET /auth/callback, where the sign-in service sends the person back.
export async function callback(request: Request): Promise<Response> {
  const forgetFlow = setCookie("auth_flow", "", 0);
  const flow = unseal("flow", readCookie(request.headers.get("cookie"), cookieName("auth_flow")), Date.now());
  if (!flow || typeof flow.state !== "string" || typeof flow.nonce !== "string" || typeof flow.verifier !== "string" || typeof flow.next !== "string") {
    return failure(400, "This sign-in has expired.", [forgetFlow]);
  }
  let tokens: Awaited<ReturnType<typeof client.authorizationCodeGrant>>;
  try {
    // Built from AUTH_ORIGIN, never from the request's own host: the service compares this address with
    // the one login sent, and behind a proxy the request's host is not the public one.
    const current = new URL(CALLBACK_PATH + new URL(request.url).search, origin());
    tokens = await client.authorizationCodeGrant(await oidc(), current, { expectedState: flow.state, expectedNonce: flow.nonce, pkceCodeVerifier: flow.verifier });
  } catch (error) {
    console.error("auth: sign-in did not complete:", error instanceof Error ? error.message : error);
    return failure(400, "Sign-in did not complete.", [forgetFlow]);
  }
  const claims = tokens.claims();
  if (!claims || !tokens.id_token) return failure(400, "Sign-in did not complete.", [forgetFlow]);
  // The address is who the person is to the app, so one nobody vouched for is refused.
  if (typeof claims.email !== "string" || claims.email_verified !== true) return failure(403, "This account has no verified email address.", [forgetFlow]);
  const session = { sub: claims.sub, email: claims.email, name: typeof claims.name === "string" && claims.name ? claims.name : claims.email };
  return redirect(302, new URL(flow.next, origin()).href, [setCookie("auth_session", seal("session", session, SESSION_TTL_SECONDS, Date.now()), SESSION_TTL_SECONDS), idTokenCookie(tokens.id_token, SESSION_TTL_SECONDS), forgetFlow]);
}

// POST /auth/logout. Ends the app's session and then the sign-in service's own, since leaving that one open
// would sign the next visitor on this browser straight back in. The service ends its session and returns
// here only when handed the ID token it issued; without one it shows its own sign-out page instead.
export async function logout(request: Request): Promise<Response> {
  const home = new URL("/", origin()).href;
  const requestOrigin = request.headers.get("origin");
  if (requestOrigin && requestOrigin !== origin()) return new Response("Cross-site request refused", { status: 403 });
  const cookies = request.headers.get("cookie");
  const forget = [setCookie("auth_session", "", 0), idTokenCookie("", 0)];
  if (devSession() || !readSession(cookies)) return redirect(303, home, forget);
  let target = home;
  try {
    const idToken = readCookie(cookies, ID_TOKEN_COOKIE);
    target = client.buildEndSessionUrl(await oidc(), idToken ? { post_logout_redirect_uri: home, id_token_hint: idToken } : { post_logout_redirect_uri: home }).href;
  } catch (error) {
    // The app's session still ends when the service cannot be reached; only the service's own stays open.
    console.error("auth: sign-out could not reach the sign-in service:", error instanceof Error ? error.message : error);
  }
  return redirect(303, target, forget);
}
