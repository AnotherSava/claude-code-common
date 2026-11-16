#!/usr/bin/env node
// End-to-end test of module/signin.ts: a throwaway Pocket ID in Docker, a minimal app hosting the module
// (e2e-harness.mjs), and every sign-in path driven over HTTP the way a browser would drive it.
//
//   node ~/.claude/skills/auth/scripts/e2e.mjs
//
// Run it after any change to module/signin.ts and before installing the module into an app. It needs
// Docker, Node 24 or newer (Node runs the TypeScript module directly), and a checkout of the auth repo
// beside the dotfiles repo, whose compose file names the Pocket ID image to test against, so the test runs
// against the release the real service pins.
//
// Everything it creates is local and disposable: one container, removed at the end, and a scratch app under
// the dotfiles repo's ignored tmp/. Its two ports come from the ports registry.

import { execFileSync, execSync, spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, openSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { devClaim, resolvePort } from "../../ports/scripts/dev-port.mjs";

const scripts = dirname(realpathSync(fileURLToPath(import.meta.url)));
const skill = resolve(scripts, "..");
const repo = resolve(skill, "..", "..", "..");
const scratch = join(repo, "tmp", "auth-e2e");
const app = join(scratch, "app");
const compose = resolve(repo, "..", "auth", "docker-compose.yml");
const CONTAINER = "auth-skill-e2e-idp";
const CLIENT = "e2e";

if (Number(process.versions.node.split(".")[0]) < 24) throw new Error(`Node 24 or newer is needed to run the TypeScript module directly; this is ${process.versions.node}`);
if (!existsSync(compose)) throw new Error(`no checkout of the auth repo beside this one: ${compose} is missing`);
const image = /^\s*image:\s*(\S+)/m.exec(readFileSync(compose, "utf8"))?.[1];
if (!image) throw new Error(`${compose} names no image`);

const owner = devClaim(repo, "--owner");
const idpPort = resolvePort({ useCase: "auth-skill-e2e-idp", owner, notes: "Throwaway Pocket ID published on localhost by the auth skill's scripts/e2e.mjs, for the length of one test run" });
const appPort = resolvePort({ useCase: "auth-skill-e2e-app", owner, notes: "The harness app hosting module/signin.ts in the auth skill's scripts/e2e.mjs, for the length of one test run" });
const issuer = `http://localhost:${idpPort}`;
const appUrl = `http://localhost:${appPort}`;
const apiKey = randomBytes(24).toString("hex");
const sessionSecret = randomBytes(36).toString("base64url");

let failed = 0;
let passed = 0;

function check(name, ok, detail = "") {
  if (ok) passed += 1;
  else failed += 1;
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok || !detail ? "" : ` (${detail})`}`);
}

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

async function until(label, probe, timeoutMs = 90_000) {
  const end = Date.now() + timeoutMs;
  for (;;) {
    try {
      if (await probe()) return;
    } catch {
      // not listening yet
    }
    if (Date.now() > end) throw new Error(`${label} did not come up within ${timeoutMs / 1000}s`);
    await sleep(500);
  }
}

async function http(url, { method = "GET", headers = {}, body } = {}) {
  const response = await fetch(url, { method, headers, body, redirect: "manual" });
  return { status: response.status, location: response.headers.get("location"), cookies: response.headers.getSetCookie(), text: await response.text() };
}

// "name=value" pairs of every cookie a response set, ready to send back.
const sent = (cookies) => cookies.map((cookie) => cookie.split(";")[0]).join("; ");
const named = (cookies, name) => cookies.find((cookie) => cookie.startsWith(`${name}=`));

async function api(method, path, body) {
  const response = await fetch(issuer + path, { method, headers: { "X-API-Key": apiKey, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await response.text();
  if (!response.ok) throw new Error(`${method} ${path} answered ${response.status}: ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : null;
}

const idpSessions = new Map();

// A signed-in Pocket ID session for a user, as a Cookie header, the way a login code gives one. One per
// user for the whole run: Pocket ID admits five code exchanges at once from one address and then one every
// ten seconds, and a person's browser keeps its session between apps in the same way.
async function idpSession(user) {
  if (!idpSessions.has(user.id)) {
    const { token } = await api("POST", `/api/users/${user.id}/one-time-access-token`, { ttl: "15m" });
    const exchange = await http(`${issuer}/api/one-time-access-token/${token}`, { method: "POST" });
    if (exchange.status !== 200) throw new Error(`login code exchange answered ${exchange.status}`);
    idpSessions.set(user.id, sent(exchange.cookies));
  }
  return idpSessions.get(user.id);
}

// What the browser does at the sign-in service: follow the authorization request and complete the
// interaction it opens. Returns the address the service sends the browser back to, or null when it refuses.
async function authorize(authorizeUrl, idpCookie) {
  const first = await http(authorizeUrl, { headers: { cookie: idpCookie } });
  let location = first.location ?? "";
  if (location.startsWith("/interaction")) {
    const id = new URL(location, issuer).searchParams.get("interaction");
    const opened = await fetch(`${issuer}/api/oidc/interactions/${id}`, { headers: { cookie: idpCookie } });
    const interaction = await opened.json();
    if (process.env.E2E_DEBUG) console.log("interaction", opened.status, JSON.stringify(interaction));
    const completed = await fetch(`${issuer}/api/oidc/interactions/${id}/complete`, { method: "POST", headers: { cookie: idpCookie, "Content-Type": "application/json" }, body: JSON.stringify({ step: interaction.step, scopes: ["openid", "profile", "email"] }) });
    const result = await completed.json();
    if (process.env.E2E_DEBUG) console.log("complete", completed.status, JSON.stringify(result));
    location = result.redirectUrl ?? "";
  }
  return location.startsWith(`${appUrl}/auth/callback?`) ? location : null;
}

// A sign-in taken as far as the service sending the browser back, with the callback not yet made. A check
// that a callback is refused starts here: once the callback has run the code is spent, and any second use
// is refused as a replay whatever else is wrong with it.
async function begin(user, next) {
  const start = await http(`${appUrl}/auth/login${next === undefined ? "" : `?next=${encodeURIComponent(next)}`}`);
  const flow = sent(start.cookies);
  const idpCookie = await idpSession(user);
  return { start, flow, idpCookie, back: await authorize(start.location, idpCookie) };
}

async function signIn(user, next) {
  const begun = await begin(user, next);
  return { ...begun, done: begun.back ? await http(begun.back, { headers: { cookie: begun.flow } }) : null };
}

let harness;

async function startHarness(env) {
  const log = openSync(join(scratch, "harness.log"), "a");
  harness = spawn(process.execPath, ["e2e-harness.mjs"], { cwd: app, stdio: ["ignore", log, log], env: { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, E2E_APP_PORT: String(appPort), ...env } });
  await until("the harness app", async () => (await fetch(`${appUrl}/public`)).status < 600);
}

async function stopHarness() {
  if (!harness) return;
  const exited = new Promise((done) => harness.once("exit", done));
  harness.kill();
  await exited;
  harness = undefined;
}

function removeContainer() {
  try {
    execFileSync("docker", ["rm", "-f", CONTAINER], { stdio: "ignore" });
  } catch {
    // no such container
  }
}

async function main() {
  mkdirSync(app, { recursive: true });
  // No package.json in the scratch app: one there is a Node project in the dotfiles tree, which that repo's
  // commit gate then holds to its package rules. The module is copied as .mts, which Node reads as an ES
  // module without one. One command string through the shell, because npm is a .cmd file on Windows, which
  // Node will not spawn directly.
  if (!existsSync(join(app, "node_modules", "openid-client"))) execSync("npm install --prefix . openid-client@6 --no-save --no-package-lock --no-audit --no-fund", { cwd: app, stdio: "inherit" });
  copyFileSync(join(skill, "module", "signin.ts"), join(app, "signin.mts"));
  copyFileSync(join(scripts, "e2e-harness.mjs"), join(app, "e2e-harness.mjs"));

  removeContainer();
  execFileSync("docker", ["run", "-d", "--rm", "--name", CONTAINER, "-p", `127.0.0.1:${idpPort}:1411`, "-e", `APP_URL=${issuer}`, "-e", `ENCRYPTION_KEY=${randomBytes(32).toString("base64")}`, "-e", `STATIC_API_KEY=${apiKey}`, "-e", "ANALYTICS_DISABLED=true", "-e", "VERSION_CHECK_DISABLED=true", image], { stdio: ["ignore", "ignore", "inherit"] });
  await until("Pocket ID", async () => (await fetch(`${issuer}/.well-known/openid-configuration`)).ok);

  const owner = await api("POST", "/api/users", { username: "owner", email: "owner@example.com", firstName: "Olive", lastName: "Owner", emailVerified: true, isAdmin: true });
  const alice = await api("POST", "/api/users", { username: "alice", email: "alice@example.com", firstName: "Alice", lastName: "Allowed", emailVerified: true });
  const bob = await api("POST", "/api/users", { username: "bob", email: "bob@example.com", firstName: "Bob", lastName: "Unverified" });
  const carol = await api("POST", "/api/users", { username: "carol", email: "carol@example.com", firstName: "Carol", lastName: "Outside", emailVerified: true });

  console.log(`\nPocket ID ${image.split("@")[0]}\n\n== registering the app`);
  // The way the real service is driven: a key a person made under their own account, with an expiry.
  const minted = await fetch(`${issuer}/api/api-keys`, { method: "POST", headers: { cookie: await idpSession(owner), "Content-Type": "application/json" }, body: JSON.stringify({ name: "e2e registration", expiresAt: new Date(Date.now() + 60 * 60 * 1000).toISOString() }) });
  const ownerKey = (await minted.json()).token;
  const register = (adminKey) => spawnSync(process.execPath, [join(scripts, "register-app.mjs"), "--issuer", issuer, "--project", CLIENT, "--name", "E2E app", "--callback", `${appUrl}/auth/callback`, "--logout-callback", `${appUrl}/`], { encoding: "utf8", env: { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, AUTH_ADMIN_API_KEY: adminKey } });
  const registered = register(ownerKey);
  const clientSecret = registered.stdout;
  check("register-app prints the client secret alone on stdout", registered.status === 0 && /^\S{20,}$/.test(clientSecret), `${registered.status} ${registered.stderr.trim()}`);
  check("the secret is not in what register-app says on stderr", clientSecret.length > 0 && !registered.stderr.includes(clientSecret));
  const client = await api("GET", `/api/oidc/clients/${CLIENT}`);
  const group = (await api("GET", `/api/user-groups?search=${CLIENT}`)).data.find((candidate) => candidate.name === CLIENT);
  check("the client is confidential, uses PKCE, skips consent and is restricted to its group", client.isPublic === false && client.pkceEnabled === true && client.skipConsent === true && client.isGroupRestricted === true && client.allowedUserGroups?.length === 1 && client.allowedUserGroups[0].id === group?.id, JSON.stringify({ isPublic: client.isPublic, pkceEnabled: client.pkceEnabled, skipConsent: client.skipConsent, isGroupRestricted: client.isGroupRestricted, allowedUserGroups: client.allowedUserGroups?.length }));
  const members = (await api("GET", `/api/user-groups/${group.id}`)).users.map((user) => user.id);
  check("the key's own user is the group's first member", members.length === 1 && members[0] === owner.id, JSON.stringify(members));
  const repeated = register(ownerKey);
  check("registering the same app again is refused and prints no secret", repeated.status === 1 && repeated.stdout === "" && /already registered/.test(repeated.stderr), `${repeated.status} ${repeated.stderr.trim()}`);
  await api("PUT", `/api/user-groups/${group.id}/users`, { userIds: [owner.id, alice.id, bob.id] });

  const signinEnv = { AUTH_ISSUER: issuer, AUTH_CLIENT_ID: CLIENT, AUTH_CLIENT_SECRET: clientSecret, AUTH_SESSION_SECRET: sessionSecret, AUTH_ORIGIN: appUrl };
  // Production mode, so the cookies under test carry the names and attributes a deployed app sets.
  await startHarness({ ...signinEnv, NODE_ENV: "production" });
  const SESSION = "__Host-auth_session";
  const FLOW = "__Host-auth_flow";

  console.log("\n== the gate");
  const html = { accept: "text/html" };
  const nav = await http(`${appUrl}/private?a=1`, { headers: html });
  check("a page navigation without a session is sent to sign in, with its own address as next", nav.status === 302 && nav.location === `${appUrl}/auth/login?next=${encodeURIComponent("/private?a=1")}`, `${nav.status} ${nav.location}`);
  check("a fetch without a session gets 401", (await http(`${appUrl}/private`, { headers: { accept: "application/json" } })).status === 401);
  check("a public path is readable without a session", (await http(`${appUrl}/public`)).status === 200);
  check("a public pattern is readable without a session", (await http(`${appUrl}/feed/abc`)).status === 200);
  check("a path beside a public pattern is not public", (await http(`${appUrl}/feed/abc/more`)).status === 401);
  check("a POST to a public path still needs a session", (await http(`${appUrl}/public`, { method: "POST" })).status === 401);

  console.log("\n== sign-in");
  const ok = await signIn(alice, "/private?a=1");
  const request = new URL(ok.start.location);
  check("login redirects to the service's authorization endpoint", ok.start.status === 302 && ok.start.location.startsWith(`${issuer}/authorize?`), ok.start.location);
  check("the request carries the client, the callback, PKCE, state and nonce", request.searchParams.get("client_id") === CLIENT && request.searchParams.get("redirect_uri") === `${appUrl}/auth/callback` && request.searchParams.get("code_challenge_method") === "S256" && Boolean(request.searchParams.get("code_challenge")) && Boolean(request.searchParams.get("state")) && Boolean(request.searchParams.get("nonce")), request.search);
  const flowCookie = named(ok.start.cookies, FLOW) ?? "";
  check("the flow cookie is host-only, HttpOnly, Secure and SameSite=Lax", /; Path=\/; HttpOnly; SameSite=Lax; Max-Age=600; Secure$/.test(flowCookie), flowCookie.replace(/=[^;]*/, "=<value>"));
  check("the service sends an allowed, verified user back with a code", Boolean(ok.back));
  check("the callback returns the user to where they were going", ok.done?.status === 302 && ok.done.location === `${appUrl}/private?a=1`, `${ok.done?.status} ${ok.done?.location}`);
  const sessionCookie = named(ok.done?.cookies ?? [], SESSION) ?? "";
  check("the session cookie is host-only, HttpOnly, Secure, SameSite=Lax and lasts 30 days", /; Path=\/; HttpOnly; SameSite=Lax; Max-Age=2592000; Secure$/.test(sessionCookie), sessionCookie.replace(/=[^;]*/, "=<value>"));
  check("the callback forgets the flow cookie", /Max-Age=0/.test(named(ok.done?.cookies ?? [], FLOW) ?? ""));
  const idTokenCookie = named(ok.done?.cookies ?? [], "auth_id_token") ?? "";
  check("the ID token is kept for sign-out in a cookie only the logout path receives", /; Path=\/auth\/logout; HttpOnly; SameSite=Lax; Max-Age=2592000; Secure$/.test(idTokenCookie), idTokenCookie.replace(/=[^;]*/, "=<value>"));
  const session = sessionCookie.split(";")[0];
  const inside = await http(`${appUrl}/private?a=1`, { headers: { cookie: session } });
  const who = inside.status === 200 ? JSON.parse(inside.text).session : null;
  check("the session names the user by subject, address and name", who?.sub === alice.id && who?.email === "alice@example.com" && who?.name === "Alice Allowed", JSON.stringify(who));
  check("login with a session already present goes straight to next", (await http(`${appUrl}/auth/login?next=/private`, { headers: { cookie: session } })).location === `${appUrl}/private`);

  console.log("\n== refused sign-ins");
  const replay = await http(ok.back, { headers: { cookie: ok.flow } });
  check("a replayed callback is refused and issues no session", replay.status === 400 && !named(replay.cookies, SESSION), `${replay.status}`);
  const forged = await begin(alice, "/private");
  const wrongState = new URL(forged.back);
  wrongState.searchParams.set("state", "forged");
  const tampered = await http(wrongState.href, { headers: { cookie: forged.flow } });
  check("a callback with a changed state is refused", tampered.status === 400 && !named(tampered.cookies, SESSION), `${tampered.status}`);
  const bare = await begin(alice, "/private");
  const noFlow = await http(bare.back);
  check("a callback without the flow cookie is refused", noFlow.status === 400 && !named(noFlow.cookies, SESSION), `${noFlow.status}`);
  const one = await http(`${appUrl}/auth/login`);
  const other = await begin(alice, "/private");
  const crossed = await http(other.back, { headers: { cookie: sent(one.cookies) } });
  check("a callback presented with another sign-in's flow cookie is refused", crossed.status === 400 && !named(crossed.cookies, SESSION), `${crossed.status}`);
  const unverified = await signIn(bob, "/private");
  check("a user whose address is not verified is refused with 403 and no session", unverified.done?.status === 403 && !named(unverified.done.cookies, SESSION), `${unverified.done?.status}`);
  const outside = await signIn(carol, "/private");
  check("the service sends a user outside the app's group nowhere", outside.back === null);

  console.log("\n== where sign-in may return to");
  for (const next of ["//evil.example/x", "/.//evil.example/x", "/a/..//evil.example/x", "https://evil.example/x", "/\\evil.example", "/auth/logout", "evil"]) {
    const result = await signIn(alice, next);
    check(`next=${next} lands on the app's own home page`, result.done?.location === `${appUrl}/`, `${result.done?.location}`);
  }

  console.log("\n== session cookies that must not work");
  // Valid JSON naming someone else under the genuine signature: only the signature check can refuse it.
  const [body, signature] = session.split("=")[1].split(".");
  const renamed = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(body, "base64url").toString("utf8")), sub: carol.id, email: "carol@example.com" })).toString("base64url");
  check("a session cookie whose payload names someone else is no session", (await http(`${appUrl}/private`, { headers: { cookie: `${SESSION}=${renamed}.${signature}` } })).status === 401);
  const asSession = `${SESSION}=${sent(one.cookies).split("=")[1]}`;
  check("a flow cookie presented as a session is no session", (await http(`${appUrl}/private`, { headers: { cookie: asSession } })).status === 401);
  Object.assign(process.env, signinEnv, { NODE_ENV: "production" });
  const { readSession } = await import(pathToFileURL(join(app, "signin.mts")).href);
  check("the session reads back in this process", readSession(session)?.sub === alice.id);
  check("the session is no session a day past its 30 days", readSession(session, Date.now() + 31 * 24 * 60 * 60 * 1000) === null);

  console.log("\n== sign-out");
  const foreign = await http(`${appUrl}/auth/logout`, { method: "POST", headers: { cookie: session, origin: "https://evil.example" } });
  check("a sign-out posted from another origin is refused and clears nothing", foreign.status === 403 && foreign.cookies.length === 0, `${foreign.status}`);
  const nobody = await http(`${appUrl}/auth/logout`, { method: "POST", headers: { origin: appUrl } });
  check("a sign-out with no session goes home without visiting the service", nobody.status === 303 && nobody.location === `${appUrl}/`, `${nobody.status} ${nobody.location}`);
  const unnamed = await http(`${appUrl}/auth/logout`, { method: "POST", headers: { cookie: session, origin: appUrl } });
  const manual = unnamed.location ? await http(unnamed.location, { headers: { cookie: ok.idpCookie } }) : null;
  check("a sign-out without the ID token still clears the session, and the service shows its own sign-out page", unnamed.status === 303 && /Max-Age=0/.test(named(unnamed.cookies, SESSION) ?? "") && manual?.location === `${issuer}/logout`, `${unnamed.status} ${manual?.location}`);
  const out = await http(`${appUrl}/auth/logout`, { method: "POST", headers: { cookie: `${session}; ${idTokenCookie.split(";")[0]}`, origin: appUrl } });
  const end = new URL(out.location);
  check("a sign-out clears the session and the ID token and goes to the service's end-session endpoint", out.status === 303 && /Max-Age=0/.test(named(out.cookies, SESSION) ?? "") && /Max-Age=0/.test(named(out.cookies, "auth_id_token") ?? "") && out.location.startsWith(`${issuer}/api/oidc/end-session?`), `${out.status}`);
  check("the end-session request names the client, the app's home page and the ID token", end.searchParams.get("client_id") === CLIENT && end.searchParams.get("post_logout_redirect_uri") === `${appUrl}/` && Boolean(end.searchParams.get("id_token_hint")), [...end.searchParams.keys()].join(","));
  const ended = await http(out.location, { headers: { cookie: ok.idpCookie } });
  check("the service ends its own session and returns to the app's home page", ended.status === 302 && ended.location === `${appUrl}/`, `${ended.status} ${ended.location}`);
  // Sign-out revokes the refresh tokens issued with that ID token and blanks the browser's session cookie.
  // It does not end that browser session on the server: the same cookie replayed afterwards was still sent
  // back with a code, until it expires. No client can change that, so the blanked cookie is what is checked.
  const idpCleared = named(ended.cookies, ok.idpCookie.split("=")[0]) ?? "";
  check("the service blanks its own session cookie in that browser", /^[^=]+=;/.test(idpCleared), idpCleared.replace(/=[^;]+/, "=<value>"));

  console.log("\n== the development user");
  await stopHarness();
  await startHarness({ NODE_ENV: "development", AUTH_DEV_USER: "dev@example.com", AUTH_ORIGIN: appUrl });
  const dev = await http(`${appUrl}/private`);
  check("AUTH_DEV_USER signs every request in outside production", dev.status === 200 && JSON.parse(dev.text).session?.sub === "dev:dev@example.com", `${dev.status}`);
  check("login with the development user goes straight to next", (await http(`${appUrl}/auth/login?next=/private`)).location === `${appUrl}/private`);
  await stopHarness();
  await startHarness({ ...signinEnv, NODE_ENV: "production", AUTH_DEV_USER: "dev@example.com" });
  check("AUTH_DEV_USER in production is an error, never a sign-in", (await http(`${appUrl}/private`)).status === 500);
}

try {
  await main();
} finally {
  await stopHarness();
  removeContainer();
}

console.log(`\n${passed} passed, ${failed} failed`);
// Set and left to drain: on Windows, process.exit() while fetch is still closing a socket aborts Node.
process.exitCode = failed ? 1 : 0;
