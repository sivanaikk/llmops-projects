"""Idempotently create LiteLLM teams + virtual keys from teams.yaml.

    LITELLM_MASTER_KEY=sk-local-master python scripts/bootstrap_teams.py

Keys are written to `.keys.env` (git-ignored) so the other projects can pick
them up, e.g. `ACCOUNT_INTEL_PROD_KEY=sk-...`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parents[1]
BASE = os.getenv("GATEWAY_URL", "http://localhost:4000").rstrip("/")
MASTER = os.getenv("LITELLM_MASTER_KEY", "sk-local-master")
TEAM_FIELDS = ("models", "max_budget", "budget_duration", "rpm_limit", "tpm_limit")
KEY_FIELDS = ("max_budget", "rpm_limit", "tpm_limit", "models")


def env_name(alias: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", alias.upper()) + "_KEY"


def main() -> int:
    spec = yaml.safe_load((HERE / "teams.yaml").read_text())
    client = httpx.Client(base_url=BASE, headers={"Authorization": f"Bearer {MASTER}"}, timeout=30)

    existing_teams = {t["team_alias"]: t for t in client.get("/team/list").raise_for_status().json() if t.get("team_alias")}
    lines = []
    for team in spec["teams"]:
        alias = team["team_alias"]
        body = {k: team[k] for k in TEAM_FIELDS if k in team}
        if alias in existing_teams:
            team_id = existing_teams[alias]["team_id"]
            client.post("/team/update", json={"team_id": team_id, **body}).raise_for_status()
            print(f"updated team {alias}")
        else:
            team_id = client.post("/team/new", json={"team_alias": alias, **body}).raise_for_status().json()["team_id"]
            print(f"created team {alias}")

        for key in team.get("keys", []):
            key_alias = key["key_alias"]
            info = client.get("/key/list", params={"key_alias": key_alias, "return_full_object": "true"})
            if info.status_code == 200 and info.json().get("keys"):
                print(f"  key {key_alias} exists (not rotating)")
                continue
            body = {"team_id": team_id, "key_alias": key_alias, "metadata": {"team": alias}}
            body.update({k: key[k] for k in KEY_FIELDS if k in key})
            secret = client.post("/key/generate", json=body).raise_for_status().json()["key"]
            lines.append(f"{env_name(key_alias)}={secret}")
            print(f"  created key {key_alias}")

    if lines:
        out = HERE / ".keys.env"
        with out.open("a") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote {len(lines)} new key(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
