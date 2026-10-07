from __future__ import annotations

RECIPE_INTENT_PREFIX = "recipe:"
LEGACY_RECIPE_INTENT_PREFIX = "custom_skill:"
RECIPE_STATUS_INTENT = "recipe_status"
LEGACY_RECIPE_STATUS_INTENT = "skill_status"
RECIPE_CONFIRMATION_REASON = "recipe_confirmation"
LEGACY_RECIPE_CONFIRMATION_REASON = "custom_skill_confirmation"
RECIPE_EXECUTION_CAPABILITY = "recipe"
LEGACY_RECIPE_EXECUTION_CAPABILITY = "custom_skill"
RECIPE_LEGACY_SOURCE = "custom_skill"
RECIPE_MANIFEST_SOURCE = "stored_recipe_manifest"
DIRECT_SSH_RECIPE_ID = "direct-ssh-command"
RECIPE_MANIFEST_MISSING_ERROR = "recipe_manifest_missing"
LEGACY_RECIPE_MANIFEST_MISSING_ERROR = "custom_skill_manifest_missing"
RECIPE_RUNTIME_SKILL_NAME_PREFIX = "recipe_"
LEGACY_RECIPE_RUNTIME_SKILL_NAME_PREFIX = "custom_skill_"
RECIPE_SSH_ERROR_PREFIX = "recipe_ssh_"
LEGACY_RECIPE_SSH_ERROR_PREFIX = "custom_skill_ssh_"
RECIPE_SSH_NONZERO_EXIT_ERROR = f"{RECIPE_SSH_ERROR_PREFIX}nonzero_exit"


def build_recipe_intent(recipe_id: str) -> str:
    clean_id = str(recipe_id or "").strip()
    return f"{RECIPE_INTENT_PREFIX}{clean_id}" if clean_id else RECIPE_INTENT_PREFIX


def is_recipe_intent(intent: str) -> bool:
    clean = str(intent or "").strip()
    return clean.startswith(RECIPE_INTENT_PREFIX) or clean.startswith(LEGACY_RECIPE_INTENT_PREFIX)


def recipe_id_from_intent(intent: str) -> str:
    clean_intent = str(intent or "").strip()
    for prefix in (RECIPE_INTENT_PREFIX, LEGACY_RECIPE_INTENT_PREFIX):
        if clean_intent.startswith(prefix):
            return clean_intent.split(":", 1)[1].strip()
    return ""


def build_recipe_runtime_skill_name(recipe_id: str) -> str:
    return f"{RECIPE_RUNTIME_SKILL_NAME_PREFIX}{str(recipe_id or '').strip()}"


def is_recipe_execution_capability(capability: str) -> bool:
    clean = str(capability or "").strip().lower()
    return clean in {RECIPE_EXECUTION_CAPABILITY, LEGACY_RECIPE_EXECUTION_CAPABILITY}


def is_recipe_confirmation_reason(reason: str) -> bool:
    clean = str(reason or "").strip()
    return clean in {RECIPE_CONFIRMATION_REASON, LEGACY_RECIPE_CONFIRMATION_REASON}


def is_recipe_status_intent(intent: str) -> bool:
    clean = str(intent or "").strip()
    return clean in {RECIPE_STATUS_INTENT, LEGACY_RECIPE_STATUS_INTENT}


def recipe_ssh_error(code: str, detail: str = "") -> str:
    clean_code = str(code or "").strip()
    base = f"{RECIPE_SSH_ERROR_PREFIX}{clean_code}" if clean_code else RECIPE_SSH_ERROR_PREFIX.rstrip("_")
    clean_detail = str(detail or "").strip()
    return f"{base}:{clean_detail}" if clean_detail else base
