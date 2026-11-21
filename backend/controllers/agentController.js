// Express side of approval and safety.
// Express is a thin, careful proxy to the Python agent service:
//   POST /api/agent/chat        -> Python /agent/chat     (answer, or a build awaiting approval)
//   POST /api/agent/approve     -> Python /agent/approve  (human decision on that exact build)
//   POST /api/cart/add-build    -> Python /agent/cart     (only an approved, unchanged, in-stock build)
//   POST /api/chat/compatibility -> Python /agent/check   (the code checker; FAILS SAFE)
// The rules live in Python (code decides); Express checks input shape and never invents a result.

const AGENT_URL = process.env.AGENT_SERVICE_URL || "http://127.0.0.1:8001";
const THREAD_RE = /^[A-Za-z0-9._@:-]{1,128}$/;
const HASH_RE = /^[0-9a-f]{64}$/;
const MAX_MESSAGE = 500;
const VERDICTS = new Set(["compatible", "incompatible", "could_not_verify"]);

function couldNotVerify(reason) {
  // isCompatible is null, not true: "we don't know" must never look like "compatible".
  return { status: "could_not_verify", isCompatible: null, reason };
}

function createAgentController({
  fetchImpl = globalThis.fetch,
  baseUrl = AGENT_URL,
  chatTimeoutMs = 180000,   // a full build with a local model can take a few minutes
  checkTimeoutMs = 10000,
  cartTimeoutMs = 15000,
} = {}) {
  async function callAgent(path, body, timeoutMs, clientIp) {
    const res = await fetchImpl(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Client-IP": clientIp || "" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    return { status: res.status, data };
  }

  // Pass Python's answer through. Network error/timeout -> 503, never a made-up success.
  async function proxy(res, path, body, timeoutMs, clientIp) {
    try {
      const { status, data } = await callAgent(path, body, timeoutMs, clientIp);
      if (!data) return res.status(502).json({ status: "error", error: "The agent service sent no answer." });
      return res.status(status).json(data);
    } catch (err) {
      console.error(`Agent service call ${path} failed:`, err.name, err.message);
      return res.status(503).json({ status: "error", error: "The AI service is not reachable. Please try again later." });
    }
  }

  const bad = (res, error) => res.status(400).json({ status: "error", error });

  return {
    chat: async (req, res) => {
      const { message, threadId } = req.body || {};
      if (typeof message !== "string" || !message.trim()) return bad(res, "message is required.");
      if (message.length > MAX_MESSAGE) return bad(res, `message must be at most ${MAX_MESSAGE} characters.`);
      if (typeof threadId !== "string" || !THREAD_RE.test(threadId)) return bad(res, "threadId is invalid.");
      return proxy(res, "/agent/chat", { message, thread_id: threadId }, chatTimeoutMs, req.ip);
    },

    approve: async (req, res) => {
      const { threadId, buildHash, approved } = req.body || {};
      if (typeof threadId !== "string" || !THREAD_RE.test(threadId)) return bad(res, "threadId is invalid.");
      if (typeof buildHash !== "string" || !HASH_RE.test(buildHash)) return bad(res, "buildHash is invalid.");
      if (typeof approved !== "boolean") return bad(res, "approved must be true or false.");
      return proxy(res, "/agent/approve", { thread_id: threadId, build_hash: buildHash, approved }, cartTimeoutMs, req.ip);
    },

    addBuildToCart: async (req, res) => {
      const { threadId, buildHash } = req.body || {};
      if (typeof threadId !== "string" || !THREAD_RE.test(threadId)) return bad(res, "threadId is invalid.");
      if (typeof buildHash !== "string" || !HASH_RE.test(buildHash)) return bad(res, "buildHash is invalid.");
      return proxy(res, "/agent/cart", { thread_id: threadId, build_hash: buildHash }, cartTimeoutMs, req.ip);
    },

    // Fail safe: ANY problem (bad answer, error code, timeout, service down) -> could_not_verify.
    // The old version answered "compatible" when its AI call failed (fail open).
    checkCompatibility: async (req, res) => {
      const { currentBuild, newItem } = req.body || {};
      const items = Array.isArray(currentBuild) && newItem ? [...currentBuild, newItem] : null;
      const ids = items && items.map((item) => item && item.id);
      if (!ids || ids.some((id) => typeof id !== "string" || !id)) {
        return res.status(400).json(couldNotVerify("Bad request: currentBuild must be a list of parts and newItem a part."));
      }
      try {
        const { status, data } = await callAgent("/agent/check", { part_ids: ids, partial: true }, checkTimeoutMs, req.ip);
        const verdict = data && data.verdict;
        if (status !== 200 || !verdict || !VERDICTS.has(verdict.status)) {
          return res.status(503).json(couldNotVerify("Could not verify compatibility: the checker did not give a valid answer."));
        }
        const problems = (verdict.problems || []).join(" | ");
        if (verdict.status === "incompatible") {
          return res.json({ status: "incompatible", isCompatible: false, reason: problems });
        }
        if (verdict.status === "could_not_verify") {
          return res.json(couldNotVerify(`Could not verify compatibility: ${problems || "missing data."}`));
        }
        const unknowns = verdict.unknowns || [];
        return res.json({
          status: "compatible",
          isCompatible: true,
          reason: unknowns.length
            ? `No problems found by code (could not check yet: ${unknowns.join(", ")}).`
            : "No problems found by code.",
        });
      } catch (err) {
        console.error("Compatibility check failed:", err.name, err.message);
        return res.status(503).json(couldNotVerify("Could not verify compatibility: the checker is unavailable."));
      }
    },
  };
}

module.exports = { createAgentController };
