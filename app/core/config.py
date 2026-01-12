from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "Citizen Services Tracker"
    env: str = "dev"
    mongo_uri: str = Field("mongodb://localhost:27017", env="MONGO_URI")
    mongo_db: str = Field("cst", env="MONGO_DB")

    id_prefix: str = Field("CST", env="ID_PREFIX")
    duplicate_radius_m: int = Field(250, env="DUPLICATE_RADIUS_M")
    duplicate_window_hours: int = Field(24, env="DUPLICATE_WINDOW_HOURS")
    sla_scan_interval_seconds: int = Field(60, env="SLA_SCAN_INTERVAL_SECONDS")

    default_priority: str = Field("P3", env="DEFAULT_PRIORITY")
    priority_by_category: Dict[str, str] = Field(default_factory=dict)

    default_sla_policy: Dict[str, object] = Field(
        default_factory=lambda: {
            "policy_id": "default",
            "target_hours": 72,
            "breach_threshold_hours": 96,
            "escalation_steps": [
                {"after_hours": 48, "action": "notify_supervisor"},
                {"after_hours": 72, "action": "auto_escalate"},
            ],
        }
    )
    sla_policies: Dict[str, Dict[str, object]] = Field(default_factory=dict)

    class Config:
        env_file = ".env"

    @classmethod
    def parse_dict_env(cls, value: str) -> Dict[str, object]:
        if not value:
            return {}
        return json.loads(value)

    @classmethod
    def parse_priority_env(cls, value: str) -> Dict[str, str]:
        if not value:
            return {}
        return json.loads(value)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if isinstance(settings.sla_policies, str):
        settings.sla_policies = Settings.parse_dict_env(settings.sla_policies)
    if isinstance(settings.priority_by_category, str):
        settings.priority_by_category = Settings.parse_priority_env(
            settings.priority_by_category
        )
    return settings
