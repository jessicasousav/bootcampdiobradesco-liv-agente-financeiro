"""Liv - Educadora Financeira de Financiamento Imobiliário (interface Streamlit).

Executar:  streamlit run src/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import calculadora as calc  # noqa: E402
import prompts  # noqa: E402
from agent import responder  # noqa: E402
from conhecimento import carregar_perfil  # noqa: E402
from llm import LLMError, config_do_ambiente  # noqa: E402

st.set_page_config(page_title="Liv | Financiamento Imobiliário", page_icon="🏠", layout="centered")

SUGESTOES = [
    "Qual a diferença entre SAC e Price?",
    "Posso usar meu FGTS na entrada?",
    "Que custos existem além da entrada?",
    "O que é CET e por que comparar?",
]


@st.cache_resource
def _config():
    try:
        return config_do_ambiente(), None
    except LLMError as e:  # configuração incompleta: cai para o modo offline e avisa
        from llm import Config

        return Config(), str(e)


cfg, erro_cfg = _config()
perfil_completo = carregar_perfil()

# ------------------------------------------------------------------ estado
st.session_state.setdefault("mensagens", [{"role": "assistant", "content": prompts.BOAS_VINDAS, "fontes": []}])
st.session_state.setdefault("simulacao", None)
st.session_state.setdefault("pendente", None)

# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.header("🏠 Liv")
    st.caption(cfg.descricao)
    if erro_cfg:
        st.warning(erro_cfg + " Rodando em modo offline.")

    usar_perfil = st.toggle("Usar meu perfil (dados fictícios)", value=True)
    perfil = perfil_completo if usar_perfil else None
    if perfil:
        with st.expander("Ver perfil"):
            st.write(
                f"**{perfil['nome']}**, {perfil['idade']} anos · renda bruta {calc.brl(perfil['renda_bruta_mensal'])}\n\n"
                f"Objetivo: {perfil['objetivo']}\n\n"
                f"Entrada: {calc.brl(perfil['entrada_disponivel'])} + FGTS {calc.brl(perfil['saldo_fgts'])}"
            )

    st.divider()
    st.subheader("Simulador SAC / Price")
    st.caption("As contas são feitas pelo código, não pelo modelo de IA.")
    p = perfil or {}
    with st.form("simulador"):
        valor = st.number_input("Valor do imóvel (R$)", 50_000.0, 20_000_000.0, float(p.get("valor_imovel_alvo", 400_000)), 10_000.0)
        entrada = st.number_input(
            "Entrada (R$, já somando FGTS)", 0.0, 20_000_000.0, float(p.get("entrada_disponivel", 60_000) + p.get("saldo_fgts", 0)), 5_000.0
        )
        anos = st.slider("Prazo (anos)", 1, 35, int(p.get("prazo_desejado_anos", 30)))
        taxa = st.number_input("Taxa de juros efetiva (% ao ano)", 1.0, 40.0, 11.0, 0.1, help="Valor hipotético: use a taxa da proposta real do seu banco.")
        sistema = st.radio("Sistema", ["SAC", "Price"], horizontal=True)
        with st.expander("Encargos opcionais"):
            seguro = st.number_input("Seguros (% ao mês sobre o saldo)", 0.0, 1.0, 0.0, 0.005, format="%.3f")
            tarifa = st.number_input("Tarifa mensal (R$)", 0.0, 500.0, 0.0, 5.0)
        enviar = st.form_submit_button("Simular", use_container_width=True)

    if enviar:
        try:
            st.session_state.simulacao = calc.simular(valor, entrada, anos * 12, taxa, sistema, seguro, tarifa)
            st.session_state.sim_params = dict(
                valor_imovel=valor, entrada=entrada, prazo_meses=anos * 12, taxa_anual_pct=taxa,
                seguro_mensal_pct=seguro, tarifa_mensal=tarifa,
            )
        except ValueError as e:
            st.session_state.simulacao = None
            st.error(str(e))

    sim = st.session_state.simulacao
    if sim:
        st.success("Simulação ativa: pergunte à Liv sobre ela.")
        st.metric("Primeira parcela", calc.brl(sim.primeira_parcela))
        st.metric("Última parcela", calc.brl(sim.ultima_parcela))
        st.metric("Total de juros", calc.brl(sim.total_juros))
        renda = (perfil or {}).get("renda_bruta_mensal")
        if renda:
            pct = sim.primeira_parcela / renda * 100
            (st.success if pct <= 30 else st.warning)(f"Parcela = {pct:.0f}% da renda (referência: até 30%)")
        with st.expander("Comparar SAC x Price"):
            s1, s2 = calc.comparar(**st.session_state.sim_params)
            st.table(
                {
                    "": ["1ª parcela", "Última parcela", "Total de juros", "Total pago"],
                    "SAC": [calc.brl(s1.primeira_parcela), calc.brl(s1.ultima_parcela), calc.brl(s1.total_juros), calc.brl(s1.total_pago_financiamento)],
                    "Price": [calc.brl(s2.primeira_parcela), calc.brl(s2.ultima_parcela), calc.brl(s2.total_juros), calc.brl(s2.total_pago_financiamento)],
                }
            )

    st.divider()
    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.mensagens = st.session_state.mensagens[:1]
        st.rerun()

# ------------------------------------------------------------------ chat
st.title("🏠 Liv")
st.caption("Educadora financeira para quem vai financiar um imóvel. Conteúdo educativo, não é oferta nem aprovação de crédito.")

for m in st.session_state.mensagens:
    with st.chat_message(m["role"], avatar="🏠" if m["role"] == "assistant" else None):
        st.markdown(m["content"])
        if m.get("fontes"):
            st.caption("Fontes: " + " · ".join(m["fontes"]))

if len(st.session_state.mensagens) == 1:
    cols = st.columns(2)
    for i, s in enumerate(SUGESTOES):
        if cols[i % 2].button(s, key=f"sug{i}", use_container_width=True):
            st.session_state.pendente = s

entrada_chat = st.chat_input("Pergunte sobre financiamento imobiliário...")
pergunta = entrada_chat or st.session_state.pendente
st.session_state.pendente = None

if pergunta:
    historico = [{"role": m["role"], "content": m["content"]} for m in st.session_state.mensagens]
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant", avatar="🏠"):
        with st.spinner("Pensando..."):
            r = responder(pergunta, historico, perfil, st.session_state.simulacao, cfg)
        st.markdown(r.texto)
        if r.fontes:
            st.caption("Fontes: " + " · ".join(r.fontes))
    st.session_state.mensagens.append({"role": "assistant", "content": r.texto, "fontes": r.fontes})
