"""Clients for the model API calls (MAKI, OpenAI)"""

import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from openai import OpenAI

from llm_ontology_leakage.core.config import base_model, web_tool_calls


@dataclass(frozen=True)
class Completion:
    """Model response and reason the generation ended"""

    text: str
    finish_reason: str | None
    web_search_actions: tuple[dict, ...] = ()  # what the model did: search (queries, sources, results), open_page (url), find_in_page (url, pattern)
    web_citations: tuple[str, ...] = ()  # urls the answer cites

    usage: dict | None = None  # token usage of the request (input, output, reasoning), stored for web search runs

    @property
    def web_searches(self) -> int:
        """Number of completed web tool calls of this answer (search, open_page, find_in_page), each counts once"""
        return sum(a["status"] == "completed" for a in self.web_search_actions)


@dataclass(frozen=True)
class TokenLogprobs:
    """Log probabilities of every token of an input text (used for Min-K%)"""

    tokens: list[str]
    logprobs: list[float | None]


class CompletionClient(Protocol):
    """Interface implemented by every inference client"""

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int,
        system: str | None = None,
    ) -> Completion:
        """Return the model's raw output to the prompt (system is only used by the synthetic generator)"""
        ...

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        """Return the log probabilities of every token of the input text (used for Min-K%)"""
        ...

    def allow_web_search(self, n: int) -> None:
        """"Allow n more web search requests (a sampled run allows as many as it sends)"""
        ...


class MakiClient:
    """Inference via the MAKI API"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        """Set up MakiClient"""
        base_url = base_url or os.environ.get("MAKI_BASE_URL")  # from .env (loaded in main.py)
        if not base_url:
            raise RuntimeError(
                "MAKI endpoint not configured, set the MAKI_BASE_URL (and MAKI_API_KEY) "
                "environment variables, or pass base_url/api_key to MakiClient."
            )
        api_key = api_key or os.environ.get("MAKI_API_KEY") or "unused"
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
            max_retries=0,
        )

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int,
        system: str | None = None,
    ) -> Completion:
        """Send the prompt and return the model's answer"""
        messages = ([{"role": "system", "content": system}] if system else []) + [  # system only used for synthetic ontology generation
            {"role": "user", "content": prompt}
        ]
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]

        return Completion(text=choice.message.content or "", finish_reason=choice.finish_reason)

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        """Fetch log probabilities of every token of the input text (used for Min-K%)"""
        response = self._client.completions.create(
            model=model, prompt=text, max_tokens=0, echo=True, logprobs=0  # echo the prompt while generating nothing
        )
        lp = response.choices[0].logprobs
        return TokenLogprobs(tokens=list(lp.tokens), logprobs=list(lp.token_logprobs))

    def allow_web_search(self, n: int) -> None:
        """MAKI has no web search, nothing to allow"""


WEB_SEARCH_OUTPUT_RESERVE = 512  # extra output tokens for web search requests


def _web_search_actions(response) -> tuple[dict, ...]:
    """Every web action of the answer with its details"""
    actions = []
    for item in response.output:
        if item.type != "web_search_call":
            continue
        a = item.action
        if a is None:
            actions.append({"type": None})
        elif a.type == "search":
            actions.append({"type": "search", "queries": a.queries or ([a.query] if a.query else []), "sources": [s.url for s in (a.sources or [])]})
        elif a.type == "open_page":
            actions.append({"type": "open_page", "url": a.url})
        elif a.type == "find_in_page":
            actions.append({"type": "find_in_page", "url": a.url, "pattern": a.pattern})
        else:
            actions.append({"type": a.type})
        actions[-1]["status"] = item.status  # completed, or searching when the limit blocked the call
        results = getattr(item, "results", None)  # text snippets the model read
        if results is not None:
            actions[-1]["results"] = list(results)  # plain dicts: type, title, url, snippet
    return tuple(actions)


def _usage(response) -> dict | None:
    """Token usage of the request: input, output and the hidden reasoning tokens inside the output"""
    u = getattr(response, "usage", None)
    if u is None:
        return None
    details = getattr(u, "output_tokens_details", None)
    return {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "reasoning_tokens": getattr(details, "reasoning_tokens", None)}


def _web_citations(response) -> tuple[str, ...]:
    """The urls the answer text cites, in order and without repeats"""
    urls = []
    for item in response.output:
        if item.type == "message":
            for part in item.content:
                for annotation in getattr(part, "annotations", None) or []:
                    if annotation.type == "url_citation":
                        urls.append(annotation.url)
    return tuple(dict.fromkeys(urls))


class OpenAIClient:
    """Inference via OpenAI"""

    def __init__(self, api_key: str | None = None) -> None:
        """Set up OpenAI client"""
        self._web_search_left = 0  # web search requests left, only sampled run raises this
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI endpoint not configured, set the OPENAI_API_KEY "
                "environment variable, or pass api_key to OpenAIClient."
            )
        self._client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(300.0, connect=10.0),
            max_retries=2,
        )

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int,
        system: str | None = None,
    ) -> Completion:
        """Send the prompt and return the model's answer"""
        tool_calls = web_tool_calls(model)  # 0 without web search, 1 for +web, 3 for +web3
        web_search = tool_calls > 0
        if web_search:
            if self._web_search_left <= 0:
                raise RuntimeError("no web search requests left for this client, only sampled runs (--sample) allow them")
            self._web_search_left -= 1

        response = self._client.responses.create(
            model=base_model(model),
            input=prompt,
            temperature=temperature,
            reasoning={"effort": "none"},  # measuring memorization, so reasoning should have no big impact
            # tool call (its queries) and reasoning around it are output tokens and count against max_output_tokens (search results come back as input tokens)
            max_output_tokens=max_tokens + WEB_SEARCH_OUTPUT_RESERVE * tool_calls,  # one reserve per allowed call
            **({"instructions": system} if system else {}),
            # model decides whether to use web search, at most tool_calls calls
            **({"tools": [{"type": "web_search"}], "max_tool_calls": tool_calls,
                # found URLs (sources) and the text snippets the model read (results)
                "include": ["web_search_call.action.sources", "web_search_call.results"]} if web_search else {}),
        )
        if response.status == "completed":
            finish = "stop"
        elif response.status == "incomplete" and response.incomplete_details:
            reason = response.incomplete_details.reason
            finish = "length" if reason == "max_output_tokens" else reason
        else:
            finish = response.status
        completion = Completion(
            text=response.output_text or "", finish_reason=finish,
            web_search_actions=_web_search_actions(response), web_citations=_web_citations(response),
            usage=_usage(response) if web_search else None,
        )
        calls = sum(1 for a in completion.web_search_actions if a["status"] == "completed")  # count every completed call (search, open_page, find_in_page)
        if web_search and calls > tool_calls:  # should never happen, if it does the run stops
            raise RuntimeError(f"{calls} web tool calls in one request, the limit is {tool_calls}, the API ignored max_tool_calls")
        return completion

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        """Min-K% needs prompt token logprobs, which OpenAI API does not offer"""
        raise NotImplementedError(
            "The OpenAI API returns log-probabilities for generated output "
            "tokens only. There is no echo mode for prompt tokens, so Min-K% "
            "cannot run against it. Use a MAKI model for Min-K%."
        )

    def allow_web_search(self, n: int) -> None:
        """Allow n more web search requests (a sampled run allows as many as it sends)"""
        self._web_search_left += n


class MockClient:
    """Test client"""

    def __init__(self, answer: str = "foaf:Person") -> None:
        self.answer = answer

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int,
        system: str | None = None,
    ) -> Completion:
        return Completion(text=self.answer, finish_reason="stop")

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        tokens = text.split()
        logprobs = [None] + [
            -0.5 - (sum(map(ord, tok)) % 80) / 10.0 for tok in tokens[1:]
        ]
        return TokenLogprobs(tokens=tokens, logprobs=logprobs)

    def allow_web_search(self, n: int) -> None:
        """The test client sends nothing, nothing to allow"""
