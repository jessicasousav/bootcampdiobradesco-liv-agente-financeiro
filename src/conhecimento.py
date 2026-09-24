"""Base de conhecimento da Liv: carregamento e busca (BM25 em Python puro).

Escolha de design: busca lexical simples, sem embeddings nem serviços externos.
Vantagens: roda offline, é explicável e determinística (bom para avaliar e evitar alucinação).
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Limiares de confiança da busca (calibrados em data/casos_teste.json, ver docs/04-metricas.md)
MIN_SCORE = 2.0
MIN_COBERTURA = 0.5


TERMOS_GENERICOS = {"financiamento", "financiar", "imovel", "imobiliario", "casa", "apartamento"}


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


_STOPWORDS_BRUTAS = """
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre e ou mas que se ao aos
pelo pela pelos pelas como qual quais quando onde quem quanto quanta quantos quantas eh sao ser foi era eu me meu
minha meus minhas voce vc te seu sua seus suas ele ela eles elas isso isto esse essa esses essas este esta estes
estas aquilo ja mais menos muito muita muitos muitas tem ter tenho pode posso podem preciso precisa precisar
fazer faz funciona vale pena entre ate tambem so sim nao vou vai ha algum alguma quero queria gostaria saber
dar dou da aqui la sao ficar fica ficam
explica explique explicar fala falar conta contar ensina ensinar mostra mostrar diz dizer pra mim
caixa itau bradesco santander bb inter c6 nubank sicoob sicredi btg safra pela pelo
"""
STOPWORDS = {normalizar(p) for p in _STOPWORDS_BRUTAS.split()}


def _radical(palavra: str) -> str:
    """Stemming bem simples para plurais em português (mesma regra para base e pergunta)."""
    if len(palavra) > 5 and palavra.endswith(("oes", "aes")):
        return palavra[:-3] + "ao"
    if len(palavra) > 4 and palavra.endswith("ais"):  # nominais -> nominal, mensais -> mensal
        return palavra[:-3] + "al"
    if len(palavra) > 4 and palavra.endswith("s"):
        return palavra[:-1]
    return palavra


def tokenizar(texto: str, remover_stopwords: bool = True) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalizar(texto))
    if remover_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return [_radical(t) for t in tokens]


@dataclass
class Trecho:
    id: str
    titulo: str
    texto: str
    tags: list[str]
    tipo: str  # "conceito" ou "linha"


@dataclass
class Resultado:
    trecho: Trecho
    score: float
    cobertura: float


class BaseConhecimento:
    def __init__(self, trechos: list[Trecho], k1: float = 1.5, b: float = 0.75):
        self.trechos = trechos
        self.k1, self.b = k1, b
        self._docs: list[Counter] = []
        self._vocab: list[set[str]] = []
        for t in trechos:
            titulo = tokenizar(t.titulo)
            tags = tokenizar(" ".join(t.tags))
            corpo = tokenizar(t.texto)
            # Título e tags valem mais (repetidos 3x) do que o corpo do texto
            tokens = titulo * 3 + tags * 3 + corpo
            self._docs.append(Counter(tokens))
            self._vocab.append(set(titulo) | set(tags) | set(corpo))
        self._tam = [sum(c.values()) for c in self._docs]
        self._media = sum(self._tam) / max(len(self._tam), 1)
        n = len(self._docs)
        df: Counter = Counter()
        for c in self._docs:
            df.update(c.keys())
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.vocabulario = set(df)

    def _bm25(self, consulta: list[str], i: int) -> float:
        doc, tam = self._docs[i], self._tam[i]
        score = 0.0
        for t in set(consulta):
            f = doc.get(t, 0)
            if not f:
                continue
            norm = f + self.k1 * (1 - self.b + self.b * tam / self._media)
            score += self._idf[t] * f * (self.k1 + 1) / norm
        return score

    def buscar(self, pergunta: str, k: int = 3, filtrar: bool = True) -> list[Resultado]:
        """Retorna até k trechos. Com filtrar=True, só devolve resultados confiáveis."""
        consulta = tokenizar(pergunta)
        if not consulta:
            return []
        unicos = set(consulta)
        # Pergunta só com termos genéricos ("como funciona o financiamento?"): responde com a introdução ao tema
        if filtrar and unicos <= TERMOS_GENERICOS:
            intro = next((t for t in self.trechos if t.id == "financiamento_basico"), None)
            return [Resultado(intro, MIN_SCORE, 1.0)] if intro else []
        resultados = []
        for i, trecho in enumerate(self.trechos):
            score = self._bm25(consulta, i)
            if score <= 0:
                continue
            cobertura = len(unicos & self._vocab[i]) / len(unicos)
            resultados.append(Resultado(trecho, score, cobertura))
        resultados.sort(key=lambda r: r.score, reverse=True)
        if filtrar:
            resultados = [r for r in resultados if r.score >= MIN_SCORE and r.cobertura >= MIN_COBERTURA]
        return resultados[:k]


def carregar_base() -> BaseConhecimento:
    conceitos = json.loads((DATA_DIR / "base_conhecimento.json").read_text(encoding="utf-8"))["conceitos"]
    linhas = json.loads((DATA_DIR / "linhas_financiamento.json").read_text(encoding="utf-8"))["linhas"]
    trechos = [Trecho(c["id"], c["titulo"], c["texto"], c.get("tags", []), "conceito") for c in conceitos]
    for l in linhas:
        texto = f"{l['caracteristicas']} Para quem: {l['para_quem']} Atenção: {l['atencao']}"
        trechos.append(Trecho(l["id"], l["nome"], texto, l.get("tags", []), "linha"))
    return BaseConhecimento(trechos)


def carregar_perfil() -> dict:
    return json.loads((DATA_DIR / "perfil_cliente.json").read_text(encoding="utf-8"))
