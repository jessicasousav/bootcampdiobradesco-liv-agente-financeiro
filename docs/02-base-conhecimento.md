# 2. Base de Conhecimento

## Dados utilizados

O repositório base da DIO traz dados de um agente de investimentos (`transacoes.csv`, `produtos_financeiros.json` etc.). Como o tema deste projeto é **financiamento imobiliário**, a base foi adaptada mantendo a mesma lógica (dados do cliente + catálogo + histórico), com conteúdo educativo próprio.

| Arquivo | Formato | Conteúdo | Uso no agente |
|---|---|---|---|
| `base_conhecimento.json` | JSON | 31 conceitos: SAC, Price, juros, CET, seguros, FGTS, documentos, custos, portabilidade, inadimplência, etc. | Fonte principal das respostas (busca BM25) |
| `linhas_financiamento.json` | JSON | 5 linhas: SBPE, Minha Casa Minha Vida, SFI, construção/reforma, home equity | Também indexado na busca (equivale ao catálogo de produtos) |
| `perfil_cliente.json` | JSON | Perfil **fictício** (renda, entrada, FGTS, objetivo, nível de conhecimento) | Personalização e teste "a parcela cabe na renda?" |
| `historico_atendimento.csv` | CSV | Atendimentos anteriores (tema, pergunta, resolvido) | Referência de dúvidas reais mais frequentes; base para novos conceitos |
| `casos_teste.json` | JSON | 37 perguntas de recuperação, 21 de guardrails e 5 de conteúdo | Avaliação automatizada (`src/evaluate.py`) |

O `transacoes.csv` do repositório base não foi usado porque não faz sentido para este caso de uso (não há histórico de gastos a analisar).

## Estrutura de cada conceito

```json
{
  "id": "sac",
  "titulo": "SAC - Sistema de Amortização Constante",
  "tags": ["sac", "amortizacao constante", "parcela decrescente"],
  "texto": "No SAC, a parte do saldo devedor que você amortiza é a mesma todo mês..."
}
```

- `id`: identificador estável (usado nos testes e nas fontes)
- `titulo` e `tags`: termos que a pessoa costuma usar; **pesam 3x mais** na busca
- `texto`: explicação curta e didática (40 a 90 palavras), com ressalvas quando a regra varia por banco

## Estratégia de integração

1. **Carga:** `conhecimento.carregar_base()` lê os JSON e transforma conceitos e linhas em "trechos".
2. **Normalização:** minúsculas, sem acentos, sem stopwords e com stemming simples de plural (`nominais → nominal`, `parcelas → parcela`).
3. **Busca:** BM25 com reforço de título/tags. Cada resultado traz `score` e `cobertura` (fração dos termos da pergunta presentes no trecho).
4. **Limiar de confiança:** só passam trechos com `score ≥ 2.0` e `cobertura ≥ 0.5`. Sem trecho confiável, o agente diz que não sabe.
5. **Contexto:** os melhores trechos, o perfil e a simulação ativa entram no prompt como **única fonte permitida** de fatos.
6. **Transparência:** os títulos dos trechos usados aparecem como "Fontes" em cada resposta.

### Exemplo de contexto montado para o LLM

```
CONTEXTO (única fonte permitida para fatos):

[Trechos da base de conhecimento]
### SAC ou Price: qual escolher
SAC: parcela inicial mais alta que cai com o tempo, menor total de juros...

[Perfil informado pela pessoa]
- Renda bruta mensal (R$): 8500.0
- Nível de conhecimento: iniciante

[Simulação calculada pelo sistema]
Simulação SAC: imóvel R$ 400.000,00, entrada R$ 85.000,00, financiado R$ 315.000,00...
Primeira parcela: R$ 3.626,40. Com renda bruta de R$ 8.500,00, a primeira parcela compromete 42.7% da renda (acima da referência de 30%).

Pergunta da pessoa: Minha parcela cabe no meu bolso?
```

## Como ampliar a base
1. Adicione um objeto em `data/base_conhecimento.json` (id único, título, tags com as palavras que as pessoas usam, texto curto).
2. Adicione um caso em `data/casos_teste.json` com o `id` esperado.
3. Rode `python src/evaluate.py` para garantir que nada piorou.

## Cuidados com o conteúdo
- Nada de taxas, tetos ou limites "de hoje": onde há números de mercado (30% da renda, 20% de entrada, 3% a 5% de custos), o texto os apresenta como **referência geral** e orienta a confirmar com a instituição.
- Dados de perfil são fictícios, sem informação pessoal real.
