"""Pydantic v2 schemas for pika configuration files."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///pika.db"


class CacheConfig(BaseModel):
    l1_max_size: int = 1000
    l2_ttl: int = 3600


class VectorDBConfig(BaseModel):
    provider: str = "lancedb"
    path: str = ".lance"
    db_schema: str = "pika"


class ObservabilityConfig(BaseModel):
    langfuse_enabled: bool = False
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"


class OptimizationConfig(BaseModel):
    dspy_lm: str = "openai/gpt-4o-mini"


class AgnoGlobalConfig(BaseModel):
    """Global Agno Agent kwargs applied to every agent unless overridden."""

    enable_agentic_memory: bool = False
    enable_user_memories: bool = False
    add_memories_to_context: bool = False
    add_history_to_context: bool = True
    num_history_runs: int = 5
    search_past_sessions: bool = False
    enable_agentic_state: bool = False


class SchedulerConfig(BaseModel):
    """Agno AgentOS cron scheduler (SchedulePoller)."""

    enabled: bool = False
    poll_interval: int = 15
    default_timezone: str = "Asia/Kolkata"
    base_url: Optional[str] = None


class HermesCompatConfig(BaseModel):
    """Hermes / agentskills compatibility settings."""

    skills_dirs: List[str] = []
    credentials_dir: Optional[str] = None


class McpConfig(BaseModel):
    """Expose AgentOS over MCP so external shells (e.g. Hermes) can drive pika agents."""

    enabled: bool = False


class PikaSettings(BaseModel):
    default_agent: str = "orchestrator"
    database: DatabaseConfig = DatabaseConfig()
    cache: CacheConfig = CacheConfig()
    vectordb: VectorDBConfig = VectorDBConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    optimization: OptimizationConfig = OptimizationConfig()
    agno: AgnoGlobalConfig = AgnoGlobalConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    hermes: HermesCompatConfig = HermesCompatConfig()
    mcp: McpConfig = McpConfig()
    credentials_dir: Optional[str] = None

    model_config = {"extra": "allow"}


class LLMProviderConfig(BaseModel):
    name: str = "openai"
    model: str = "gpt-4o-mini"

    model_config = {"extra": "allow"}


class CorrectionConfig(BaseModel):
    enabled: bool = True
    top_k: int = 5
    score_threshold: float = 0.75


class AgentCacheConfig(BaseModel):
    enabled: bool = True
    ttl: int = 3600


class MemoryConfig(BaseModel):
    enabled: bool = False
    enable_user_memories: bool = True
    add_to_context: bool = True


class KnowledgeConfig(BaseModel):
    provider: str = "lancedb"
    collection: str = "knowledge"
    embedder: str = "openai"
    max_results: int = 10


class AgentConfig(BaseModel):
    llm_provider: Optional[LLMProviderConfig] = None
    agent_kwargs: Dict[str, Any] = {}
    cache: AgentCacheConfig = AgentCacheConfig()
    corrections: CorrectionConfig = CorrectionConfig()
    memory: MemoryConfig = MemoryConfig()
    knowledge: Optional[KnowledgeConfig] = None

    model_config = {"extra": "allow"}


class TeamConfig(BaseModel):
    llm_provider: Optional[LLMProviderConfig] = None
    team_kwargs: Dict[str, Any] = {}

    model_config = {"extra": "allow"}


class ToolConfig(BaseModel):
    model_config = {"extra": "allow"}
