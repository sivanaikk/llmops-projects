"""LiteLLM adapter for guardkit (02-guardrails).

Loaded by the proxy via config.yaml:

    guardrails:
      - guardrail_name: airt-guardkit
        litellm_params:
          guardrail: custom_guardrail.GuardkitGuardrail
          mode: [pre_call, post_call]
          default_on: true

Policy is selected by the caller's LiteLLM team alias, so product teams get
different strictness without separate gateways.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import HTTPException
from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.guardrails import GuardrailEventHooks

from guardkit import load_policies
from guardkit.gateway import GuardrailBlocked, guard_request, guard_response_text

POLICY_FILE = os.getenv("GUARDKIT_POLICIES", "/app/plugins/02-guardrails/policies.yaml")


class GuardkitGuardrail(CustomGuardrail):
    def __init__(self, **kwargs: Any):
        self.policies = load_policies(POLICY_FILE)
        super().__init__(**kwargs)

    def _policy(self, user_api_key_dict) -> Any:
        team = getattr(user_api_key_dict, "team_alias", None) or "default"
        return self.policies.get(team, self.policies["default"])

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type) -> dict:
        if not self.should_run_guardrail(data=data, event_type=GuardrailEventHooks.pre_call):
            return data
        policy = self._policy(user_api_key_dict)
        # Per-request salt: pseudonyms are consistent inside one request but
        # can't be joined across requests.
        salt = data.get("litellm_call_id") or str(uuid.uuid4())
        try:
            report = guard_request(data, policy, salt=salt)
        except GuardrailBlocked as e:
            verbose_proxy_logger.warning("guardkit blocked request: policy=%s reasons=%s", e.policy, e.reasons)
            raise HTTPException(status_code=400, detail={"error": "guardrail_blocked", "policy": e.policy, "reasons": e.reasons}) from e
        if report.actions:
            data.setdefault("metadata", {})["guardkit"] = {"policy": report.policy, "actions": report.actions}
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict, response) -> Any:
        if not self.should_run_guardrail(data=data, event_type=GuardrailEventHooks.post_call):
            return response
        policy = self._policy(user_api_key_dict)
        for choice in getattr(response, "choices", None) or []:
            msg = getattr(choice, "message", None)
            if msg is not None and isinstance(msg.content, str):
                try:
                    msg.content, _ = guard_response_text(msg.content, policy)
                except GuardrailBlocked as e:
                    raise HTTPException(status_code=400, detail={"error": "guardrail_blocked_output", "reasons": e.reasons}) from e
        return response
