"""Calculadora de financiamento (SAC e Price).

Regra de ouro do projeto: quem faz as contas é o código, nunca o LLM.
O modelo apenas explica os números que esta calculadora produz.

Premissas (simplificadas e didáticas):
- A taxa informada é a efetiva anual; a mensal é (1 + a.a.)^(1/12) - 1.
- Seguros (MIP/DFI) entram como % ao mês sobre o saldo devedor e a tarifa de administração como valor fixo mensal.
- Não considera correção por TR/IPCA nem amortizações extraordinárias.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LIMITE_RENDA = 0.30  # regra geral de mercado: parcela inicial <= 30% da renda bruta


@dataclass
class Simulacao:
    sistema: str
    valor_imovel: float
    entrada: float
    valor_financiado: float
    prazo_meses: int
    taxa_anual_pct: float
    taxa_mensal_pct: float
    primeira_parcela: float
    ultima_parcela: float
    total_pago_financiamento: float  # soma das parcelas (inclui juros e encargos)
    total_juros: float
    total_encargos: float  # seguros + tarifas
    renda_minima_sugerida: float
    parcelas: list[float] = field(default_factory=list, repr=False)

    @property
    def custo_total_com_entrada(self) -> float:
        return self.total_pago_financiamento + self.entrada


def taxa_mensal(taxa_anual_pct: float) -> float:
    return (1 + taxa_anual_pct / 100) ** (1 / 12) - 1


def simular(
    valor_imovel: float,
    entrada: float,
    prazo_meses: int,
    taxa_anual_pct: float,
    sistema: str = "SAC",
    seguro_mensal_pct: float = 0.0,
    tarifa_mensal: float = 0.0,
) -> Simulacao:
    sistema = sistema.strip().upper()
    if sistema not in {"SAC", "PRICE"}:
        raise ValueError("Sistema deve ser SAC ou Price.")
    if valor_imovel <= 0:
        raise ValueError("O valor do imóvel deve ser maior que zero.")
    if entrada < 0 or entrada >= valor_imovel:
        raise ValueError("A entrada deve ser maior ou igual a zero e menor que o valor do imóvel.")
    if not 1 <= prazo_meses <= 420:
        raise ValueError("O prazo deve ficar entre 1 e 420 meses (35 anos).")
    if taxa_anual_pct <= 0 or taxa_anual_pct > 60:
        raise ValueError("A taxa anual deve ser maior que 0 e no máximo 60%.")
    if seguro_mensal_pct < 0 or tarifa_mensal < 0:
        raise ValueError("Seguro e tarifa não podem ser negativos.")

    pv = valor_imovel - entrada
    i = taxa_mensal(taxa_anual_pct)
    n = prazo_meses
    seg = seguro_mensal_pct / 100

    saldo = pv
    parcelas: list[float] = []
    juros_total = 0.0
    encargos_total = 0.0
    pmt_price = pv * i / (1 - (1 + i) ** -n)

    for _ in range(n):
        juros = saldo * i
        amort = pv / n if sistema == "SAC" else pmt_price - juros
        encargos = saldo * seg + tarifa_mensal
        parcelas.append(amort + juros + encargos)
        juros_total += juros
        encargos_total += encargos
        saldo -= amort

    return Simulacao(
        sistema="SAC" if sistema == "SAC" else "Price",
        valor_imovel=valor_imovel,
        entrada=entrada,
        valor_financiado=pv,
        prazo_meses=n,
        taxa_anual_pct=taxa_anual_pct,
        taxa_mensal_pct=i * 100,
        primeira_parcela=parcelas[0],
        ultima_parcela=parcelas[-1],
        total_pago_financiamento=sum(parcelas),
        total_juros=juros_total,
        total_encargos=encargos_total,
        renda_minima_sugerida=parcelas[0] / LIMITE_RENDA,
        parcelas=parcelas,
    )


def comparar(**kwargs) -> tuple[Simulacao, Simulacao]:
    """Simula SAC e Price com os mesmos parâmetros."""
    kwargs.pop("sistema", None)
    return simular(sistema="SAC", **kwargs), simular(sistema="PRICE", **kwargs)


def brl(valor: float) -> str:
    """Formata em reais no padrão brasileiro: R$ 1.234,56."""
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def resumo_texto(sim: Simulacao, renda_bruta: float | None = None) -> str:
    """Resumo em texto com os números já calculados (usado no contexto do LLM e no modo offline)."""
    linhas = [
        f"Simulação {sim.sistema}: imóvel {brl(sim.valor_imovel)}, entrada {brl(sim.entrada)}, "
        f"financiado {brl(sim.valor_financiado)}, prazo {sim.prazo_meses} meses "
        f"({sim.prazo_meses / 12:.1f} anos), taxa {sim.taxa_anual_pct:.2f}% a.a. "
        f"({sim.taxa_mensal_pct:.4f}% a.m.).",
        f"Primeira parcela: {brl(sim.primeira_parcela)}. Última parcela: {brl(sim.ultima_parcela)}.",
        f"Total pago no financiamento: {brl(sim.total_pago_financiamento)} "
        f"(juros {brl(sim.total_juros)}"
        + (f", seguros e tarifas {brl(sim.total_encargos)}" if sim.total_encargos > 0 else "")
        + ").",
        f"Renda bruta mensal mínima sugerida (parcela inicial = 30% da renda): {brl(sim.renda_minima_sugerida)}.",
    ]
    if renda_bruta:
        pct = sim.primeira_parcela / renda_bruta * 100
        situacao = "dentro" if pct <= LIMITE_RENDA * 100 else "acima"
        linhas.append(
            f"Com renda bruta de {brl(renda_bruta)}, a primeira parcela compromete {pct:.1f}% da renda "
            f"({situacao} da referência de 30%)."
        )
    return "\n".join(linhas)
