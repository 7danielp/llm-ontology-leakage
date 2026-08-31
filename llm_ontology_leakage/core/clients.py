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


@dataclass(frozen=True)
class TokenLogprobs:
    """Log probabilities of every token of an input text (used for Min-K%)"""

    tokens: list[str]
    logprobs: list[float | None]


class CompletionClient(Protocol):
    """Interface implemented by every inference client"""

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int
    ) -> Completion:
        """Return the model's raw output to the prompt"""
        ...

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        """Return the log probabilities of every token of the input text (used for Min-K%)"""
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


class OpenAIClient:
    """Inference via OpenAI"""

    def __init__(self, api_key: str | None = None) -> None:
        """Set up OpenAI client"""
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI endpoint not configured, set the OPENAI_API_KEY "
                "environment variable, or pass api_key to OpenAIClient."
            )
        self._client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
            max_retries=0,
        )

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int,
        system: str | None = None,
    ) -> Completion:
        """Send the prompt and return the model's answer"""
        web_search = model.endswith("+web")

        response = self._client.responses.create(
            model=model.removesuffix("+web"),
            input=prompt,
            temperature=temperature,
            reasoning={"effort": "none"},  # measuring memorization, so reasoning should have no big impact
            max_output_tokens=max_tokens,
            **({"instructions": system} if system else {}),
            **({"tools": [{"type": "web_search"}]} if web_search else {}),
        )
        if response.status == "completed":
            finish = "stop"
        elif response.status == "incomplete" and response.incomplete_details:
            reason = response.incomplete_details.reason
            finish = "length" if reason == "max_output_tokens" else reason
        else:
            finish = response.status
        return Completion(text=response.output_text or "", finish_reason=finish)

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        """Min-K% needs prompt token logprobs, which OpenAI API does not offer"""
        raise NotImplementedError(
            "The OpenAI API returns log-probabilities for generated output "
            "tokens only. There is no echo mode for prompt tokens, so Min-K% "
            "cannot run against it. Use a MAKI model for Min-K%."
        )


class MockClient:
    """Test client"""

    def __init__(self, answer: str = "foaf:Person") -> None:
        self.answer = answer

    def complete(
        self, prompt: str, *, model: str, temperature: float, max_tokens: int
    ) -> Completion:
        return Completion(text=self.answer, finish_reason="stop")

    def token_logprobs(self, text: str, *, model: str) -> TokenLogprobs:
        tokens = text.split()
        logprobs = [None] + [
            -0.5 - (sum(map(ord, tok)) % 80) / 10.0 for tok in tokens[1:]
        ]
        return TokenLogprobs(tokens=tokens, logprobs=logprobs)
