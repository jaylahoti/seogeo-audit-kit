"""Claude client for audits: structured output, a per-audit budget, and a cost ledger.

Every call records stage, model, tokens, searches, cost and time, so the report's Trace
can show exactly what Claude did and what it cost. Calls stop once the audit's budget is
spent: the pipeline keeps going on rules alone rather than running up a bill.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

# USD per million tokens (input, output). Haiku's rate applies to prompts up to 100K tokens;
# prompts here are capped well below that.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
WEB_SEARCH_USD = 0.01  # $10 per 1,000 searches
# Sonnet 5.5: if a request is declined, the API re-runs it on a fallback model in the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class BudgetExceeded(Exception):
    """The audit's Claude budget is spent; callers fall back to rule-only results."""


@dataclass
class Call:
    stage: str
    model: str
    input_tokens: int
    output_tokens: int
    searches: int
    cost: float
    ms: int
    ok: bool
    note: str = ""


@dataclass
class Ledger:
    budget: float
    calls: list[Call] = field(default_factory=list)

    @property
    def spent(self) -> float:
        return sum(c.cost for c in self.calls)

    def for_stage(self, stage: str) -> dict:
        cs = [c for c in self.calls if c.stage == stage]
        return {
            "calls": len(cs),
            "cost": round(sum(c.cost for c in cs), 5),
            "input_tokens": sum(c.input_tokens for c in cs),
            "output_tokens": sum(c.output_tokens for c in cs),
            "searches": sum(c.searches for c in cs),
            "models": sorted({c.model for c in cs}),
        }

    def to_json(self) -> dict:
        return {"budget": self.budget, "spent": round(self.spent, 5), "calls": [asdict(c) for c in self.calls]}


def price(model: str, input_tokens: int, output_tokens: int, searches: int = 0) -> float:
    pin, pout = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    return input_tokens * pin / 1e6 + output_tokens * pout / 1e6 + searches * WEB_SEARCH_USD


class Claude:
    """One per audit. `enabled` is False when no API key is configured."""

    def __init__(self, budget: float | None = None):
        self.enabled = bool(settings.anthropic_api_key)
        self.ledger = Ledger(budget=budget if budget is not None else settings.max_audit_cost_usd)
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=2) if self.enabled else None

    def _check_budget(self, model: str, est_input_tokens: int, max_tokens: int, searches: int = 0):
        # Worst case for this call (full max_tokens of output) must fit in what's left.
        worst = price(model, est_input_tokens, max_tokens, searches)
        if self.ledger.spent + worst > self.ledger.budget:
            raise BudgetExceeded(f"Claude budget of ${self.ledger.budget:.2f} reached")

    def _record(self, stage: str, model: str, usage: Any, searches: int, started: float, ok: bool, note: str = ""):
        tin = getattr(usage, "input_tokens", 0) or 0
        tout = getattr(usage, "output_tokens", 0) or 0
        self.ledger.calls.append(Call(stage, model, tin, tout, searches, round(price(model, tin, tout, searches), 6),
                                      round((time.perf_counter() - started) * 1000), ok, note))

    async def parse(
        self, *, stage: str, model: str, system: str, user: str, schema: type[T],
        max_tokens: int = 2000, effort: str = "low",
    ) -> T | None:
        """Structured call. Returns a validated `schema` instance, or None if Claude declined
        or ran out of tokens. Raises BudgetExceeded before spending past the budget."""
        if not self._client:
            return None
        self._check_budget(model, len(system + user) // 3, max_tokens)
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_format": schema, "output_config": {"effort": effort},
        }
        try:
            if model.startswith("claude-sonnet-5-5"):
                res = await self._client.beta.messages.parse(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
            else:
                res = await self._client.messages.parse(**kwargs)
        except anthropic.APIStatusError as e:
            self.ledger.calls.append(Call(stage, model, 0, 0, 0, 0.0, round((time.perf_counter() - started) * 1000), False, f"API {e.status_code}"))
            return None
        except anthropic.APIConnectionError:
            self.ledger.calls.append(Call(stage, model, 0, 0, 0, 0.0, round((time.perf_counter() - started) * 1000), False, "connection"))
            return None
        if res.stop_reason in ("refusal", "max_tokens"):
            self._record(stage, model, res.usage, 0, started, False, res.stop_reason)
            return None
        self._record(stage, model, res.usage, 0, started, True)
        return res.parsed_output

    async def search(self, *, stage: str, model: str, system: str, question: str, max_uses: int = 2,
                     max_tokens: int = 1200) -> dict | None:
        """Answer a question with web search. Returns {text, cited_urls, result_urls} or None."""
        if not self._client:
            return None
        self._check_budget(model, 15000, max_tokens, max_uses)  # search results inflate input tokens
        started = time.perf_counter()
        last_error = ""
        for tool_type in ("web_search_20260209", "web_search_20250305"):
            try:
                res = await self._client.messages.create(
                    model=model, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": question}],
                    tools=[{"type": tool_type, "name": "web_search", "max_uses": max_uses}],
                )
                break
            except anthropic.BadRequestError as e:  # older tool variant for models without the new one
                last_error = e.message
                continue
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                self.ledger.calls.append(Call(stage, model, 0, 0, 0, 0.0, round((time.perf_counter() - started) * 1000), False, type(e).__name__))
                return None
        else:
            self.ledger.calls.append(Call(stage, model, 0, 0, 0, 0.0, round((time.perf_counter() - started) * 1000), False, last_error[:80]))
            return None

        text, cited, results = [], [], []
        for block in res.content:
            if block.type == "text":
                text.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        cited.append(url)
            elif block.type == "web_search_tool_result":
                content = block.content
                if isinstance(content, list):  # an error result is an object, not a list
                    results.extend(r.url for r in content if getattr(r, "url", None))
        searches = getattr(getattr(res.usage, "server_tool_use", None), "web_search_requests", None) or (1 if results else 0)
        self._record(stage, model, res.usage, searches, started, res.stop_reason != "refusal")
        return {"text": "".join(text), "cited_urls": list(dict.fromkeys(cited)),
                "result_urls": list(dict.fromkeys(results)), "searches": searches}
