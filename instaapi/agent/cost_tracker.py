"""
Cost Tracker — Token Usage & Cost Monitoring
=============================================
Track API usage costs per provider, per session, and cumulative.

Pricing (approximate, per 1M tokens, as of Feb 2026):
    GPT-5.2:              $10.00 in / $30.00 out
    GPT-4.1-mini:         $0.40 in / $1.60 out
    Gemini 2.5 Flash:     $0.15 in / $0.60 out (free tier available)
    Gemini 2.5 Pro:       $1.25 in / $10.00 out
    Claude Sonnet 4:      $3.00 in / $15.00 out
    Claude Opus 4.6:      $15.00 in / $75.00 out
    DeepSeek Chat:        $0.14 in / $0.28 out
    Groq Llama 3.3 70B:   $0.59 in / $0.79 out
    Grok 3:               $3.00 in / $15.00 out
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("instaapi.agent.cost_tracker")

# Pricing per 1M tokens (input_cost, output_cost)
PRICING = {
    # ─── OpenAI ────────────────────────────────────
    "gpt-5.2": (10.00, 30.00),
    "gpt-5": (5.00, 15.00),
    "gpt-5-mini": (1.00, 4.00),
    "gpt-5-nano": (0.25, 1.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o3": (10.00, 40.00),
    "o3-pro": (20.00, 80.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),

    # ─── Gemini ────────────────────────────────────
    "gemini-3.1-pro": (1.25, 10.00),
    "gemini-3-pro": (1.25, 10.00),
    "gemini-3-flash": (0.15, 0.60),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.05, 0.20),
    "gemini-2.0-flash": (0.10, 0.40),

    # ─── Claude ────────────────────────────────────
    "claude-opus-4.6": (15.00, 75.00),
    "claude-sonnet-4.6": (3.00, 15.00),
    "claude-haiku-4.5": (0.80, 4.00),
    "claude-opus-4.5": (10.00, 50.00),
    "claude-sonnet-4.5": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),

    # ─── DeepSeek ──────────────────────────────────
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-coder": (0.14, 0.28),

    # ─── Groq ──────────────────────────────────────
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "qwen-qwq-32b": (0.29, 0.39),
    "deepseek-r1-distill-llama-70b": (0.59, 0.79),

    # ─── Together ──────────────────────────────────
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.88, 0.88),

    # ─── Mistral ───────────────────────────────────
    "mistral-large-latest": (2.00, 6.00),
    "mistral-medium-latest": (1.00, 3.00),
    "mistral-small-latest": (0.10, 0.30),

    # ─── Qwen ──────────────────────────────────────
    "qwen3-32b": (0.20, 0.60),
    "qwen-plus": (0.50, 1.50),

    # ─── Ollama (free, local) ──────────────────────
    "llama3.2": (0.0, 0.0),

    # ─── Perplexity ────────────────────────────────
    "sonar-pro": (3.00, 15.00),
    "sonar": (1.00, 1.00),
    "llama-3.1-sonar-large-128k-online": (1.00, 1.00),

    # ─── xAI (Grok) ───────────────────────────────
    "grok-4-latest": (3.00, 15.00),
    "grok-3-latest": (3.00, 15.00),
    "grok-2-latest": (2.00, 10.00),
}

# Default pricing for unknown models
DEFAULT_PRICING = (0.50, 2.00)


@dataclass
class UsageRecord:
    """A single API call usage record."""
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    session_id: str = ""


@dataclass
class CostSummary:
    """Aggregated cost summary."""
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    api_calls: int = 0
    by_model: Dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            f"💰 Cost Summary:",
            f"   API calls: {self.api_calls}",
            f"   Tokens: {self.total_tokens:,} "
            f"(in: {self.total_prompt_tokens:,}, out: {self.total_completion_tokens:,})",
            f"   Cost: ${self.total_cost_usd:.4f}",
        ]
        if self.by_model:
            lines.append("   By model:")
            for model, cost in sorted(self.by_model.items(), key=lambda x: -x[1]):
                lines.append(f"     {model}: ${cost:.4f}")
        return "\n".join(lines)


class CostTracker:
    """
    Track and report API usage costs.

    Usage:
        tracker = CostTracker()
        tracker.record(model="gpt-4.1-mini", prompt_tokens=500, completion_tokens=200)
        print(tracker.summary())
        tracker.save("costs.json")
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._records: List[UsageRecord] = []
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._persist_path = persist_path

        # Load existing records
        if persist_path and os.path.exists(persist_path):
            self._load(persist_path)

    def record(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        usage: Optional[Dict] = None,
    ) -> UsageRecord:
        """Record an API call's token usage."""
        if usage:
            prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
            completion_tokens = usage.get("completion_tokens", completion_tokens)

        total = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
            session_id=self._session_id,
        )

        self._records.append(record)

        # Auto-save
        if self._persist_path:
            self._save(self._persist_path)

        return record

    def summary(self, session_only: bool = False) -> CostSummary:
        """Get cost summary."""
        records = self._records
        if session_only:
            records = [r for r in records if r.session_id == self._session_id]

        summary = CostSummary()
        for r in records:
            summary.total_tokens += r.total_tokens
            summary.total_prompt_tokens += r.prompt_tokens
            summary.total_completion_tokens += r.completion_tokens
            summary.total_cost_usd += r.cost_usd
            summary.api_calls += 1
            summary.by_model[r.model] = summary.by_model.get(r.model, 0) + r.cost_usd

        return summary

    def session_cost(self) -> float:
        """Get current session cost in USD."""
        return sum(
            r.cost_usd for r in self._records
            if r.session_id == self._session_id
        )

    def format_cost(self) -> str:
        """Format current session cost as a readable string."""
        s = self.summary(session_only=True)
        if s.total_cost_usd == 0:
            return "🆓 Free (no cost)"
        elif s.total_cost_usd < 0.01:
            return f"💰 < $0.01 ({s.total_tokens:,} tokens)"
        else:
            return f"💰 ${s.total_cost_usd:.4f} ({s.total_tokens:,} tokens)"

    def reset(self):
        """Reset all records."""
        self._records.clear()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def save(self, path: str):
        """Save cost records to JSON file."""
        self._save(path)

    # ═══════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD."""
        # Find pricing — try exact match, then partial match
        pricing = PRICING.get(model)

        if not pricing:
            # Try partial matching
            model_lower = model.lower()
            for key, val in PRICING.items():
                if key in model_lower or model_lower in key:
                    pricing = val
                    break

        if not pricing:
            pricing = DEFAULT_PRICING

        input_cost, output_cost = pricing
        return (prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000

    def _save(self, path: str):
        data = [
            {
                "timestamp": r.timestamp,
                "model": r.model,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_usd": r.cost_usd,
                "session_id": r.session_id,
            }
            for r in self._records
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                self._records.append(UsageRecord(**item))
        except (json.JSONDecodeError, IOError, TypeError):
            pass
