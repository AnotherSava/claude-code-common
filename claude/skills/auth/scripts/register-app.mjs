#!/usr/bin/env node
// Register an app with the sign-in service: its group, its client restricted to that group, and the API
// key's own user as the group's first member.
//
//   AUTH_ADMIN_API_KEY=... node register-app.mjs --issuer <url> --project <compose project> --name "<App name>" \
//     --callback <url> [--callback <url> ...] --logout-callback <url> [--logout-callback <url> ...]
//
// stdout carries the client secret and nothing else, so the caller pipes it into the app's secret store
// and it never reaches a terminal or a transcript. Everything meant to be read goes to stderr.
//
// Use a key a person created under their own account: whoever the key belongs to becomes the group's first
// member, which is what lets them into the app they are registering, and stderr names them. A group that
// already exists is reused, so a run that died after creating it can be repeated. A client that already
// exists is refused: its secret was shown once and cannot be read back, and minting another is the
// service's own procedure.
//
// The calls are Pocket ID's admin API as the auth repo's docs/app-contract.md records them.

import { parseArgs } from "node:util";

// Thrown rather than exiting on the spot: on Windows, process.exit() while fetch is still closing a socket
// aborts Node with a libuv assertion and a meaningless exit status.
class Refusal extends Error {}

function fail(message) {
  throw new Refusal(message);
}

async function main() {
  const { values } = parseArgs({
    options: {
      issuer: { type: "string" },
      project: { type: "string" },
      name: { type: "string" },
      callback: { type: "string", multiple: true },
      "logout-callback": { type: "string", multiple: true },
    },
  });
  const key = process.env.AUTH_ADMIN_API_KEY;
  if (!key) fail("AUTH_ADMIN_API_KEY is not set");
  for (const option of ["issuer", "project", "name", "callback", "logout-callback"]) if (!values[option]?.length) fail(`--${option} is required`);
  const issuer = values.issuer.replace(/\/+$/, "");
  const project = values.project;

  async function api(method, path, body) {
    const response = await fetch(issuer + path, { method, headers: { "X-API-Key": key, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const text = await response.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      // an error page is not JSON; the status is what gets reported
    }
    return { status: response.status, json };
  }

  async function must(method, path, body) {
    const result = await api(method, path, body);
    if (result.status < 200 || result.status >= 300) fail(`${method} ${path} answered ${result.status}${result.json?.error ? `: ${result.json.error}` : ""}`);
    return result.json;
  }

  const me = await must("GET", "/api/users/me");
  const found = await must("GET", `/api/user-groups?search=${encodeURIComponent(project)}`);
  const group = found.data.find((candidate) => candidate.name === project) ?? (await must("POST", "/api/user-groups", { name: project, friendlyName: values.name }));

  const existing = await api("GET", `/api/oidc/clients/${encodeURIComponent(project)}`);
  if (existing.status === 200) fail(`client "${project}" is already registered; its secret cannot be read back, so mint a further one as docs/app-contract.md in the auth repo describes`);
  if (existing.status !== 404) fail(`GET /api/oidc/clients/${project} answered ${existing.status}`);

  const client = await must("POST", "/api/oidc/clients", { id: project, name: values.name, callbackURLs: values.callback, logoutCallbackURLs: values["logout-callback"], isPublic: false, pkceEnabled: true, skipConsent: true, isGroupRestricted: true });
  const secret = client.createdSecret?.secret;
  if (!secret) fail("the service created the client and returned no secret");
  await must("PUT", `/api/oidc/clients/${encodeURIComponent(project)}/allowed-user-groups`, { userGroupIds: [group.id] });

  // The membership call replaces the whole list, so the members already there are sent back with the owner.
  const members = new Set(((await must("GET", `/api/user-groups/${group.id}`)).users ?? []).map((user) => user.id));
  members.add(me.id);
  await must("PUT", `/api/user-groups/${group.id}/users`, { userIds: [...members] });

  process.stderr.write(`registered client "${project}" at ${issuer}\n  group "${project}" admits ${members.size} ${members.size === 1 ? "person" : "people"}, ${me.email ?? me.username} among them\n  callbacks: ${values.callback.join(", ")}\n  the client secret is on stdout\n`);
  process.stdout.write(secret);
}

try {
  await main();
} catch (error) {
  if (!(error instanceof Refusal)) throw error;
  process.stderr.write(`register-app: ${error.message}\n`);
  process.exitCode = 1;
}
