(function (global) {
  "use strict";

  function create(options) {
    const body = options.body;
    const brandMark = options.brandMark || null;
    const delayMs = Number.isFinite(options.delayMs) ? options.delayMs : 220;
    const schedule = options.setTimeout || global.setTimeout.bind(global);
    const cancel = options.clearTimeout || global.clearTimeout.bind(global);
    const owners = new Set();
    let pendingTimer = null;

    function render(active) {
      body.classList.toggle("app-busy", active);
      if (brandMark) {
        brandMark.classList.toggle("logo-busy", active);
      }
    }

    function clearPendingTimer() {
      if (pendingTimer === null) return;
      cancel(pendingTimer);
      pendingTimer = null;
    }

    function sync(immediate) {
      if (owners.size === 0) {
        clearPendingTimer();
        render(false);
        return;
      }
      if (immediate) {
        clearPendingTimer();
        render(true);
        return;
      }
      if (body.classList.contains("app-busy") || pendingTimer !== null) return;
      pendingTimer = schedule(function () {
        pendingTimer = null;
        if (owners.size > 0) render(true);
      }, delayMs);
    }

    function begin(owner, config) {
      if (owner === undefined || owner === null || owner === "") {
        throw new Error("A busy owner is required");
      }
      owners.add(owner);
      sync(Boolean(config && config.immediate));
      return owner;
    }

    function end(owner) {
      if (owner === undefined || owner === null || owner === "") return false;
      const removed = owners.delete(owner);
      sync(false);
      return removed;
    }

    function reset() {
      owners.clear();
      clearPendingTimer();
      render(false);
    }

    return {
      begin,
      end,
      reset,
      isBusy: function () {
        return owners.size > 0;
      },
      ownerCount: function () {
        return owners.size;
      },
    };
  }

  global.AriaBusyState = { create };
})(typeof window !== "undefined" ? window : globalThis);
