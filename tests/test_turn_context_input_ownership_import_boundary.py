from __future__ import annotations

import importlib
from pathlib import Path


def test_llm_input_contract_legacy_path_is_canonical_module_identity() -> None:
    legacy = importlib.import_module("aria.modules.llm_input_contract.contract")
    canonical = importlib.import_module("aria.modules.llm_input_contract.contract")

    assert legacy is canonical
    assert legacy.build_llm_input_contract is canonical.build_llm_input_contract
    assert legacy.llm_input_contract_diagnostics is canonical.llm_input_contract_diagnostics
    assert legacy.validated_used_learning_hint_ids is canonical.validated_used_learning_hint_ids
    assert legacy.validated_selected_personal_claim_ids is canonical.validated_selected_personal_claim_ids
