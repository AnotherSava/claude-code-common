// The smallest app that can host the sign-in module: e2e.mjs copies this beside a copy of signin.ts and
// runs it. It routes the three /auth paths to the module and puts every other path behind the module's
// gate, which is what an adopting app's proxy.ts and route files do.

import { createServer } from "node:http";

import { callback, gate, login, logout, readSession } from "./signin.mts";

const port = Number(process.env.E2E_APP_PORT);
const publicPaths = ["/public", /^\/feed\/[^/]+$/];

async function respond(request) {
  const path = new URL(request.url).pathname;
  if (path === "/auth/login" && request.method === "GET") return login(request);
  if (path === "/auth/callback" && request.method === "GET") return callback(request);
  if (path === "/auth/logout" && request.method === "POST") return logout(request);
  return gate(request, publicPaths) ?? Response.json({ path, session: readSession(request.headers.get("cookie")) });
}

createServer(async (req, res) => {
  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers)) headers.set(name, Array.isArray(value) ? value.join(", ") : value);
  let response;
  try {
    response = await respond(new Request(`http://localhost:${port}${req.url}`, { method: req.method, headers }));
  } catch (error) {
    response = new Response(`harness: ${error instanceof Error ? error.message : error}`, { status: 500 });
  }
  for (const [name, value] of response.headers) if (name !== "set-cookie") res.setHeader(name, value);
  const cookies = response.headers.getSetCookie();
  if (cookies.length) res.setHeader("set-cookie", cookies);
  res.writeHead(response.status);
  res.end(await response.text());
}).listen(port, "127.0.0.1");
