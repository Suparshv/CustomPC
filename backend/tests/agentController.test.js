// Express side of approval and safety (agentController.js).
// Run: node --test backend/tests   (no Python, Mongo or Gemini needed: fetch is faked)
const test = require("node:test");
const assert = require("node:assert/strict");
const { createAgentController } = require("../controllers/agentController");

const HASH = "a".repeat(64);

function fakeRes() {
  return {
    statusCode: 200,
    body: undefined,
    status(code) { this.statusCode = code; return this; },
    json(body) { this.body = body; return this; },
  };
}

// fetch that answers with a fixed status/body and records every call
function replyWith(status, body) {
  const calls = [];
  const fetchImpl = async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    return { ok: status < 400, status, json: async () => body };
  };
  fetchImpl.calls = calls;
  return fetchImpl;
}

const failingFetch = async () => { throw new TypeError("fetch failed: ECONNREFUSED"); };
const hangingFetch = (url, opts) => new Promise((_, reject) => {
  opts.signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "TimeoutError" })));
});

async function call(handler, body) {
  const res = fakeRes();
  await handler({ body, ip: "127.0.0.1" }, res);
  return res;
}

const BUILD = { currentBuild: [{ id: "p1" }], newItem: { id: "m1" } };

// ─── Compatibility: fail safe, never fail open ───────────────────────────────
test("compatibility: compatible verdict from the Python checker", async () => {
  const fetchImpl = replyWith(200, { verdict: { status: "compatible", problems: [], unknowns: [] } });
  const res = await call(createAgentController({ fetchImpl }).checkCompatibility, BUILD);
  assert.equal(res.body.status, "compatible");
  assert.equal(res.body.isCompatible, true);
  assert.deepEqual(fetchImpl.calls[0].body, { part_ids: ["p1", "m1"], partial: true });
  assert.match(fetchImpl.calls[0].url, /\/agent\/check$/);
});

test("compatibility: incompatible verdict lists the problems", async () => {
  const fetchImpl = replyWith(200, { verdict: { status: "incompatible", problems: ["Socket mismatch"] } });
  const res = await call(createAgentController({ fetchImpl }).checkCompatibility, BUILD);
  assert.equal(res.body.status, "incompatible");
  assert.equal(res.body.isCompatible, false);
  assert.match(res.body.reason, /Socket mismatch/);
});

const BROKEN = {
  "Python returns 503": replyWith(503, { verdict: { status: "could_not_verify" } }),
  "Python returns 500 with no verdict": replyWith(500, { detail: "boom" }),
  "Python returns 200 but no verdict": replyWith(200, { something: "else" }),
  "Python returns an unknown verdict": replyWith(200, { verdict: { status: "probably fine" } }),
  "Python is not running": failingFetch,
  "Python times out": hangingFetch,
};
for (const [name, fetchImpl] of Object.entries(BROKEN)) {
  test(`compatibility fails safe when ${name}`, async () => {
    const ctrl = createAgentController({ fetchImpl, checkTimeoutMs: 50 });
    const res = await call(ctrl.checkCompatibility, BUILD);
    assert.equal(res.body.status, "could_not_verify");
    assert.equal(res.body.isCompatible, null);           // never true
    assert.notEqual(res.statusCode, 200);
  });
}

test("compatibility: bad input is 400 and Python is not called", async () => {
  const fetchImpl = replyWith(200, {});
  const res = await call(createAgentController({ fetchImpl }).checkCompatibility, { currentBuild: "nope" });
  assert.equal(res.statusCode, 400);
  assert.equal(res.body.status, "could_not_verify");
  assert.equal(fetchImpl.calls.length, 0);
});

// ─── Cart: only an approved build ─────────────────────────────────────────────
test("cart: an approved build is added with the server's items", async () => {
  const items = [{ category: "gpu", id: "gpu_1", name: "GPU", price: 30000 }];
  const fetchImpl = replyWith(200, { status: "added", items, total: 30000 });
  const res = await call(createAgentController({ fetchImpl }).addBuildToCart, { threadId: "t1", buildHash: HASH });
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.body.items, items);
  assert.deepEqual(fetchImpl.calls[0].body, { thread_id: "t1", build_hash: HASH });
});

for (const [status, code] of [["not_approved", 403], ["expired", 410], ["build_changed", 409]]) {
  test(`cart: Python says ${status} -> ${code}, nothing added`, async () => {
    const fetchImpl = replyWith(code, { status, message: "no" });
    const res = await call(createAgentController({ fetchImpl }).addBuildToCart, { threadId: "t1", buildHash: HASH });
    assert.equal(res.statusCode, code);
    assert.equal(res.body.status, status);
    assert.equal(res.body.items, undefined);
  });
}

test("cart: missing approval details is 400 and Python is not called", async () => {
  const fetchImpl = replyWith(200, { status: "added", items: [] });
  const ctrl = createAgentController({ fetchImpl });
  assert.equal((await call(ctrl.addBuildToCart, { threadId: "t1" })).statusCode, 400);
  assert.equal((await call(ctrl.addBuildToCart, { buildHash: HASH })).statusCode, 400);
  assert.equal((await call(ctrl.addBuildToCart, { threadId: "t1", buildHash: "short" })).statusCode, 400);
  assert.equal(fetchImpl.calls.length, 0);
});

test("cart: Python down is 503, never 'added'", async () => {
  const res = await call(createAgentController({ fetchImpl: failingFetch }).addBuildToCart, { threadId: "t1", buildHash: HASH });
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.status, "error");
});

// ─── Chat and approve proxies ─────────────────────────────────────────────────
test("chat: forwards message and thread, passes the answer through", async () => {
  const fetchImpl = replyWith(200, { status: "awaiting_approval", approval: { build_hash: HASH } });
  const res = await call(createAgentController({ fetchImpl }).chat, { message: "Gaming PC", threadId: "t1" });
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.status, "awaiting_approval");
  assert.deepEqual(fetchImpl.calls[0].body, { message: "Gaming PC", thread_id: "t1" });
});

test("chat: message over 500 characters is 400 and Python is not called", async () => {
  const fetchImpl = replyWith(200, {});
  const res = await call(createAgentController({ fetchImpl }).chat, { message: "x".repeat(501), threadId: "t1" });
  assert.equal(res.statusCode, 400);
  assert.equal(fetchImpl.calls.length, 0);
});

test("chat: rate limit (429) from Python is passed through", async () => {
  const fetchImpl = replyWith(429, { status: "rate_limited" });
  const res = await call(createAgentController({ fetchImpl }).chat, { message: "Gaming PC", threadId: "t1" });
  assert.equal(res.statusCode, 429);
});

test("chat: Python down is 503 with an error status", async () => {
  const res = await call(createAgentController({ fetchImpl: failingFetch }).chat, { message: "Gaming PC", threadId: "t1" });
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.status, "error");
});

test("approve: forwards the decision; 'approved' must be a real boolean", async () => {
  const fetchImpl = replyWith(200, { status: "approved" });
  const ctrl = createAgentController({ fetchImpl });
  const ok = await call(ctrl.approve, { threadId: "t1", buildHash: HASH, approved: true });
  assert.equal(ok.statusCode, 200);
  assert.deepEqual(fetchImpl.calls[0].body, { thread_id: "t1", build_hash: HASH, approved: true });
  const bad = await call(ctrl.approve, { threadId: "t1", buildHash: HASH, approved: "true" });
  assert.equal(bad.statusCode, 400);
  assert.equal(fetchImpl.calls.length, 1);
});

test("approve: hash mismatch (409) is passed through", async () => {
  const fetchImpl = replyWith(409, { status: "hash_mismatch" });
  const res = await call(createAgentController({ fetchImpl }).approve, { threadId: "t1", buildHash: HASH, approved: true });
  assert.equal(res.statusCode, 409);
  assert.equal(res.body.status, "hash_mismatch");
});
