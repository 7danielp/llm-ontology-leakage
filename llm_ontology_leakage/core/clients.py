"""Clients for the model API calls (MAKI, OpenAI)"""

import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from openai import OpenAI


@dataclass(frozen=True)
class Completion:
    """Model response and reason the generation ended"""

    text: str
    finish_reason: str | None
    web_search_actions: tuple[dict, ...] = ()  # what the model did: search (queries, sources), open_page (url), find_in_page (url, pattern)
    web_citations: tuple[str, ...] = ()  # urls the answer cites

    @property
    def web_searches(self) -> int:
        """Number of searches (at most one per request)"""
        return sum(1 for a in self.web_search_actions if a["type"] == "search")


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


def _web_search_actions(response) -> tuple[dict, ...]:
    """Every web action of the answer with its details"""
    actions = []
    for item in response.output:
        if item.type != "web_search_call":
            continue
        a = item.action
        if a.type == "search":
            actions.append({"type": "search", "queries": a.queries or ([a.query] if a.query else []), "sources": [s.url for s in (a.sources or [])]})
        elif a.type == "open_page":
            actions.append({"type": "open_page", "url": a.url})
        else:
            actions.append({"type": "find_in_page", "url": a.url, "pattern": a.pattern})
        actions[-1]["status"] = item.status  # completed or failed
    return tuple(actions)


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
        web_search = model.endswith("+web")
        if web_search:
            if self._web_search_left <= 0:
                raise RuntimeError("no web search requests left for this client, only sampled runs (--sample) allow them")
            self._web_search_left -= 1

        response = self._client.responses.create(
            model=model.removesuffix("+web"),
            input=prompt,
            temperature=temperature,
            reasoning={"effort": "none"},  # measuring memorization, so reasoning should have no big impact
            max_output_tokens=max_tokens,
            **({"instructions": system} if system else {}),
            **({"tools": [{"type": "web_search"}], "max_tool_calls": 1} if web_search else {}),  # model decides whether to perform a web search (at most 1)
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
        )
        if completion.web_searches > 1:  # must never happen with max_tool_calls 1; stop before more money is spent
            raise RuntimeError(f"{completion.web_searches} web searches in one request, the API ignored max_tool_calls")
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
