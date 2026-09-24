"""Núcleo da Liv.

Fluxo de cada pergunta:
  1. Guardrails determinísticos (saudação, injeção de prompt, fora de escopo, taxa de hoje, garantia de crédito)
  2. Busca na base de conhecimento (BM25) com limiar de confiança
  3. Sem base confiável e sem simulação relevante -> "não tenho essa informação" (o LLM nem é chamado)
  4. Com base: LLM (se configurado) responde SÓ com o contexto; senão, modo offline monta a resposta da base
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import prompts
from calculadora import Simulacao, resumo_texto
from conhecimento import BaseConhecimento, carregar_base, normalizar
from llm import Config, LLMError, config_do_ambiente, gerar

_BASE: BaseConhecimento | None = None


def obter_base() -> BaseConhecimento:
    global _BASE
    if _BASE is None:
        _BASE = carregar_base()
    return _BASE


@dataclass
class Resposta:
    texto: str
    fontes: list[str] = field(default_factory=list)
    modo: str = "offline"  # llm | offline | guardrail
    motivo: str = ""  # saudacao | fora_escopo | injecao | taxa_atual | garantia | sem_informacao | base | llm_indisponivel


# ---------------------------------------------------------------- guardrails
_RE_INJECAO = re.compile(
    r"(ignor\w+|esquec\w+|desconsider\w+)\b.*\b(instruc\w+|regra\w*|prompt|anterior\w*)"
    r"|prompt (do )?(sistema|inicial)|system prompt|finj\w+ ser|aja como|voce agora e|modo desenvolvedor|jailbreak"
)
_RE_IDENTIDADE = re.compile(
    r"quem (e|eh|foi) (voce|vc)|(qual|como) (e )?(o )?(seu nome|voce se chama|te chamo)|o que (voce|vc) (faz|sabe fazer)|"
    r"para que (voce )?serve|voce e (um |uma )?(robo|ia|humana|humano|pessoa|bot|banco|atendente)|se apresent\w+|apresente-se"
)
_RE_FORA = re.compile(
    r"\b(acao|acoes|bolsa de valores|bitcoin|cripto\w*|ethereum|dolar|tesouro direto|fundos? de investimento|"
    r"renda variavel|day trade|forex|bolo|receita de|poema|poesia|futebol|campeonato|filme|musica|piada|"
    r"previsao do tempo|eleicao|eleicoes|programar|python|javascript)\b"
    r"|melhor (acao|investimento)|investir na bolsa"
)
# Temas próximos do assunto, mas que a base NÃO cobre: evita que uma palavra em comum gere resposta enganosa.
_RE_SEM_BASE = re.compile(
    r"imposto de renda|\birpf?\b|declarar|declaracao|inventario|heranca|divorcio|partilha|usucapiao|"
    r"terreno rural|imovel rural|na planta|financiamento de (carro|veiculo|moto)|laudemio|juros de obra"
)
_RE_PEDE_CALCULO = re.compile(r"(parcela|prestacao)\b.*\d|\d.*\b(parcela|prestacao)|\b(simula\w*|calcul\w*)\b")
_RE_TAXA_TERMOS = re.compile(r"\b(taxa|taxas|juros|cet)\b")
_RE_TAXA_ATUAL = re.compile(
    r"\b(hoje|agora|atualmente|no momento|atual)\b"
    r"|melhor banco|qual banco|banco (mais )?(barato|bom)|banco com (menor|melhor)|juros (mais )?(barato|baixo)s?|"
    r"(mais barat\w+|menores?) (juros|taxa)"
)
_RE_BANCOS = re.compile(
    r"\b(itau|bradesco|santander|caixa|banco do brasil|bb|inter|c6|nubank|sicoob|sicredi|btg|safra)\b"
)
_RE_GARANTIA = re.compile(
    r"\b(vou|consigo|serei|sou|posso ser)\s+(ser\s+)?aprovad\w*|voce garante|garant\w+ (que )?(eu )?(consigo|aprova\w*|o credito)|"
    r"tenho chance de (ser )?aprovad\w*"
)
_RE_SAUDACAO = re.compile(r"^(oi+|ola|opa|bom dia|boa tarde|boa noite|e ai|hey|hello|tudo bem)\b[\s!?.,]*(tudo bem)?[\s!?.]*$")
_RE_USA_SIMULACAO = re.compile(
    r"simula\w*|parcela\w*|pagar|meu financiamento|renda|caber|cabe|juros total|quanto (vou|vai|irei)|custa|custo"
)


def classificar(pergunta: str) -> str:
    """Retorna: saudacao, identidade, injecao, fora_escopo, taxa_atual, garantia, sem_informacao ou normal."""
    n = normalizar(pergunta).strip()
    if _RE_INJECAO.search(n):
        return "injecao"
    if _RE_IDENTIDADE.search(n):
        return "identidade"
    if _RE_FORA.search(n):
        return "fora_escopo"
    tem_taxa = bool(_RE_TAXA_TERMOS.search(n))
    if (tem_taxa and (_RE_TAXA_ATUAL.search(n) or _RE_BANCOS.search(n))) or re.search(
        r"melhor banco|qual banco|banco (mais )?(barato|bom)", n
    ):
        return "taxa_atual"
    if _RE_GARANTIA.search(n):
        return "garantia"
    if _RE_SEM_BASE.search(n):
        return "sem_informacao"
    if _RE_SAUDACAO.match(n):
        return "saudacao"
    return "normal"


_CANNED = {
    "saudacao": prompts.BOAS_VINDAS,
    "identidade": prompts.IDENTIDADE,
    "injecao": prompts.INJECAO,
    "fora_escopo": prompts.FORA_ESCOPO,
    "taxa_atual": prompts.TAXA_ATUAL,
    "garantia": prompts.GARANTIA,
    "sem_informacao": prompts.SEM_INFORMACAO,
    "calculo": prompts.CALCULO,
}


# ---------------------------------------------------------------- montagem de respostas
def _resumo_perfil(perfil: dict | None) -> str:
    if not perfil:
        return "(não informado)"
    campos = {
        "nome": "Nome",
        "idade": "Idade",
        "renda_bruta_mensal": "Renda bruta mensal (R$)",
        "nivel_conhecimento": "Nível de conhecimento",
        "objetivo": "Objetivo",
        "valor_imovel_alvo": "Valor do imóvel desejado (R$)",
        "entrada_disponivel": "Entrada disponível (R$)",
        "saldo_fgts": "Saldo de FGTS (R$)",
        "prazo_desejado_anos": "Prazo desejado (anos)",
    }
    return "\n".join(f"- {rot}: {perfil[k]}" for k, rot in campos.items() if k in perfil)


def _historico_valido(historico: list[dict] | None, max_msgs: int = 6) -> list[dict]:
    """Últimas mensagens, começando por 'user' e alternando papéis (exigência de alguns provedores)."""
    msgs = [m for m in (historico or []) if m.get("content")][-max_msgs:]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    limpo: list[dict] = []
    for m in msgs:
        if limpo and limpo[-1]["role"] == m["role"]:
            limpo[-1] = {"role": m["role"], "content": limpo[-1]["content"] + "\n" + m["content"]}
        else:
            limpo.append({"role": m["role"], "content": m["content"]})
    if limpo and limpo[-1]["role"] == "user":
        limpo.pop()  # a pergunta atual entra separadamente
    return limpo


def _montar_offline(resultados, simulacao: Simulacao | None, perfil: dict | None, usa_sim: bool) -> str:
    partes = []
    if simulacao and usa_sim:
        renda = perfil.get("renda_bruta_mensal") if perfil else None
        partes.append("**Sua simulação**\n\n" + resumo_texto(simulacao, renda).replace("\n", "\n\n"))
    if resultados:
        principal = resultados[0].trecho
        partes.append(f"**{principal.titulo}**\n\n{principal.texto}")
        extras = [r.trecho.titulo for r in resultados[1:] if r.score >= 0.6 * resultados[0].score]
        if extras:
            partes.append("Quer aprofundar? Posso explicar também: " + "; ".join(extras) + ".")
    partes.append(prompts.RODAPE)
    return "\n\n".join(partes)


def responder(
    pergunta: str,
    historico: list[dict] | None = None,
    perfil: dict | None = None,
    simulacao: Simulacao | None = None,
    cfg: Config | None = None,
) -> Resposta:
    cfg = cfg if cfg is not None else config_do_ambiente()

    # 1) guardrails
    tipo = classificar(pergunta)
    if tipo != "normal":
        return Resposta(_CANNED[tipo], modo="guardrail", motivo=tipo)

    # 1b) pedido de cálculo sem simulação ativa: quem calcula é o simulador, nunca o modelo
    if not simulacao and _RE_PEDE_CALCULO.search(normalizar(pergunta)):
        return Resposta(prompts.CALCULO, modo="guardrail", motivo="calculo")

    # 2) busca confiável
    resultados = obter_base().buscar(pergunta, k=3)
    usa_sim = bool(simulacao and _RE_USA_SIMULACAO.search(normalizar(pergunta)))

    # 3) sem base -> não inventa
    if not resultados and not usa_sim:
        return Resposta(prompts.SEM_INFORMACAO, modo="guardrail", motivo="sem_informacao")

    fontes = [r.trecho.titulo for r in resultados]
    if usa_sim:
        fontes.append("Simulação calculada (SAC/Price)")

    # 4a) LLM restrito ao contexto
    if cfg.ativo:
        contexto = prompts.TEMPLATE_CONTEXTO.format(
            trechos="\n\n".join(f"### {r.trecho.titulo}\n{r.trecho.texto}" for r in resultados) or "(nenhum trecho)",
            perfil=_resumo_perfil(perfil),
            simulacao=resumo_texto(simulacao, (perfil or {}).get("renda_bruta_mensal")) if usa_sim else "(nenhuma)",
            pergunta=pergunta,
        )
        mensagens = _historico_valido(historico) + [{"role": "user", "content": contexto}]
        try:
            texto = gerar(prompts.SYSTEM_PROMPT, mensagens, cfg)
            return Resposta(texto + "\n\n" + prompts.RODAPE, fontes, modo="llm", motivo="base")
        except LLMError:
            texto = _montar_offline(resultados, simulacao, perfil, usa_sim)
            aviso = "_Não consegui falar com o modelo agora, então respondi direto da base de conhecimento._\n\n"
            return Resposta(aviso + texto, fontes, modo="offline", motivo="llm_indisponivel")

    # 4b) modo offline
    return Resposta(_montar_offline(resultados, simulacao, perfil, usa_sim), fontes, modo="offline", motivo="base")
