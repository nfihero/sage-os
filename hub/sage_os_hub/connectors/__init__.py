"""Builds the configured agents and model providers ([agents] and [[models]] in config.toml)."""
from __future__ import annotations

import os

from ..adapters.system import router_info
from .base import AgentConnector
from .claude import ClaudeConnector
from .hermes import HermesConnector
from .hermes_api import HermesAPI
from .hermes_chat import HermesChat
from .models import ModelProvider


def build_agents(hub, cfg) -> dict[str, AgentConnector]:
    agents: list[AgentConnector] = []
    if cfg.claude_enabled:
        agents.append(ClaudeConnector(hub, hub.inbox, cfg.claude_workspaces))
    if cfg.hermes_profiles:
        api = HermesAPI(cfg.gateway, cfg.hermes_home)
        chat = HermesChat(hub, api, hub.inbox)
        agents += [HermesConnector(p, cfg.profile_labels.get(p, p), api, chat) for p in cfg.hermes_profiles]
    return {a.id: a for a in agents}


def build_providers(cfg) -> dict[str, ModelProvider]:
    providers: list[ModelProvider] = []
    if cfg.hermes_profiles:
        home = cfg.hermes_home
        providers.append(ModelProvider("hermes-router", "llama.cpp (Hermes)", f"{cfg.router}/v1", "local",
                                       "Hermes router", lambda: router_info(home).get("api_key")))
    for m in cfg.model_providers:
        env = m.get("api_key_env")
        providers.append(ModelProvider(m["id"], m.get("label", m["id"]), m["base_url"], m.get("kind", "local"),
                                       f"env {env}" if env else "", (lambda e=env: os.environ.get(e)) if env else (lambda: None)))
    return {p.id: p for p in providers}
