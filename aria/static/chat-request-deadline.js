(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.AriaChatRequestDeadline = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function createRequestDeadline(options) {
    const controller = options.controller;
    const deadlineMs = Math.max(1, Number(options.timeoutMs) || 90000);
    const now = options.now || Date.now;
    const schedule = options.setTimeout || setTimeout;
    const cancel = options.clearTimeout || clearTimeout;
    const startedAt = now();
    const phases = { headers: null, body: null, dom: null };
    let expired = false;
    let aborted = false;
    let finished = false;

    function elapsedMs() {
      return Math.max(0, Math.round(now() - startedAt));
    }

    function expire() {
      if (finished || expired) return;
      expired = true;
      if (!aborted) {
        aborted = true;
        controller.abort();
      }
    }

    const timerId = schedule(expire, deadlineMs);

    function checkpoint(phase) {
      const elapsed = elapsedMs();
      if (expired || elapsed >= deadlineMs) {
        expire();
        return false;
      }
      if (Object.prototype.hasOwnProperty.call(phases, phase)) {
        phases[phase] = elapsed;
      }
      return true;
    }

    function snapshot() {
      return {
        headersMs: phases.headers,
        bodyMs: phases.body,
        domMs: phases.dom,
        totalMs: elapsedMs(),
        deadlineMs: deadlineMs,
        timedOut: expired,
      };
    }

    function finish() {
      if (finished) return;
      finished = true;
      cancel(timerId);
    }

    return {
      checkpoint: checkpoint,
      finish: finish,
      snapshot: snapshot,
      timedOut: function () {
        if (!expired && elapsedMs() >= deadlineMs) expire();
        return expired;
      },
    };
  }

  function normalizeJobGoal(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function matchRecentAgentJob(rows, submittedMessage, submittedAtSeconds) {
    const submitted = normalizeJobGoal(submittedMessage);
    if (!submitted) return null;
    const threshold = Number(submittedAtSeconds) || 0;
    const candidates = (Array.isArray(rows) ? rows : [])
      .filter((row) => Number(row && row.created_at || 0) >= threshold)
      .filter((row) => {
        const goal = normalizeJobGoal(row && row.goal);
        if (!goal) return false;
        const length = Math.min(160, submitted.length, goal.length);
        return length > 0 && submitted.slice(0, length) === goal.slice(0, length);
      })
      .sort((left, right) => Number(right.created_at || 0) - Number(left.created_at || 0));
    return candidates.length ? candidates[0] : null;
  }

  return {
    createRequestDeadline: createRequestDeadline,
    matchRecentAgentJob: matchRecentAgentJob,
  };
});
