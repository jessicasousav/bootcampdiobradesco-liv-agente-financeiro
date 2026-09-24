"""Cliente de LLM multi-provedor, só com `requests` (sem SDKs).

Provedores: anthropic, openai (e compatíveis), gemini, ollama (local) ou none (modo offline).
Configuração por variáveis de ambiente ou arquivo .env (veja .env.example).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

MODELOS_PADRAO = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.2",
}


class LLMError(RuntimeError):
    pass


@dataclass
class Config:
    provider: str = "none"
    model: str = ""
    api_key: str = ""
    base_url: str = ""

    @property
    def ativo(self) -> bool:
        return self.provider != "none"

    @property
    def descricao(self) -> str:
        if not self.ativo:
            return "Modo offline (respostas montadas direto da base de conhecimento)"
        return f"LLM: {self.provider} / {self.model}"


def _carregar_env() -> None:
    arquivo = Path(__file__).resolve().parent.parent / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def config_do_ambiente() -> Config:
    _carregar_env()
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    chaves = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
        "ollama": "",
    }
    if not provider:  # detecta pela chave disponível
        provider = next((p for p in ("anthropic", "openai", "gemini") if chaves[p]), "none")
    if provider == "none":
        return Config()
    if provider not in MODELOS_PADRAO:
        raise LLMError(f"LLM_PROVIDER inválido: {provider}. Use anthropic, openai, gemini, ollama ou none.")
    if provider != "ollama" and not chaves[provider]:
        raise LLMError(f"Defina a chave de API do provedor '{provider}' (veja .env.example).")
    base = os.getenv("LLM_BASE_URL", "")
    if not base:
        base = {"openai": "https://api.openai.com/v1", "ollama": "http://localhost:11434/v1"}.get(provider, "")
    return Config(provider, os.getenv("LLM_MODEL", "") or MODELOS_PADRAO[provider], chaves[provider], base)


def gerar(system: str, mensagens: list[dict], cfg: Config, timeout: int = 60) -> str:
    """mensagens: [{"role": "user"|"assistant", "content": "..."}]. Retorna o texto da resposta."""
    try:
        if cfg.provider in ("openai", "ollama"):
            r = requests.post(
                f"{cfg.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {cfg.api_key or 'ollama'}"},
                json={
                    "model": cfg.model,
                    "temperature": 0.2,
                    "messages": [{"role": "system", "content": system}, *mensagens],
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

        if cfg.provider == "anthropic":
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": cfg.model,
                    "max_tokens": 700,
                    "temperature": 0.2,
                    "system": system,
                    "messages": mensagens,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"]).strip()

        if cfg.provider == "gemini":
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.model}:generateContent",
                headers={"x-goog-api-key": cfg.api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [
                        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                        for m in mensagens
                    ],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
                },
                timeout=timeout,
            )
            r.raise_for_status()
            partes = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in partes).strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Falha ao chamar o provedor {cfg.provider}: {e}") from e

    raise LLMError(f"Provedor não suportado: {cfg.provider}")
