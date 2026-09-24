# 5. Pitch (3 minutos)

Roteiro pronto para gravar em primeira pessoa. Ritmo de ~140 palavras por minuto. Para gravar: abra o app (`streamlit run src/app.py`), deixe o perfil ativado e siga as marcações de tela.

---

## 0:00 a 0:25 | O problema (gancho)

> "Comprar um imóvel é a maior dívida da vida de quase todo mundo. E a maioria das pessoas entra na negociação sem entender o que está assinando: SAC, Price, CET, MIP, DFI, TR... Num contrato de 30 anos, a pessoa pode pagar em juros mais do que o próprio valor financiado, e comparar propostas sem esse repertório sai caro."

**Tela:** título do projeto e o app aberto.

## 0:25 a 0:55 | A solução

> "Por isso criei a **Liv**, uma educadora financeira com inteligência artificial que ensina financiamento imobiliário em linguagem simples. Ela explica os conceitos, simula SAC e Price e mostra se a parcela cabe na renda de quem está comprando. E ela não vende nada: o objetivo é a pessoa chegar preparada ao banco."

**Tela:** mensagem de boas-vindas e as sugestões de perguntas.

## 0:55 a 2:00 | Demonstração

> "Vou mostrar com a Mariana, um perfil fictício: renda de 8.500 reais, 60 mil de entrada e 25 mil de FGTS, olhando um apartamento de 400 mil."

**Tela:** faça a pergunta *"Qual a diferença entre SAC e Price?"*.
> "Repare que a resposta é curta, sem jargão, e mostra as **fontes** que usou."

**Tela:** clique em *Simular* (SAC, 30 anos, 11% a.a.).
> "Aqui o simulador calcula: a primeira parcela seria de 3.626 reais. Perguntando *'Minha parcela cabe na minha renda?'*, a Liv aponta que isso compromete cerca de 43% da renda, acima da referência de 30%, e sugere caminhos: entrada maior, outro prazo ou compor renda."

**Tela:** abra *Comparar SAC x Price*.
> "Na Price a parcela inicial é menor, mas o total de juros é maior. Uma decisão que a pessoa toma com informação, não no escuro."

## 2:00 a 2:35 | Como resolvi a confiança (diferencial)

> "Em finanças, IA que inventa resposta é perigoso. Então construí quatro travas. Primeira: a IA só responde com base em uma base de conhecimento; se não encontra, diz *'não tenho essa informação'*. Segunda: **quem faz as contas é o código, não o modelo**. Terceira: ela nunca garante aprovação, nunca informa a taxa de hoje de um banco e não recomenda instituição. Quarta: proteção contra tentativas de burlar as regras."

**Tela:** pergunte *"Qual a taxa do Itaú hoje?"* e mostre a recusa educada. Depois *"Como declarar o financiamento no imposto de renda?"* e mostre o "não tenho essa informação".

## 2:35 a 3:00 | Resultados e fechamento

> "Testei com 63 casos automatizados: 100% de acerto nos guardrails e nas respostas seguras, 95% de acerto do trecho certo em primeiro lugar e cálculo validado contra valores de referência. E funciona até sem chave de API, com Claude, OpenAI, Gemini ou um modelo local. A Liv mostra como IA pode ser educativa, honesta e útil em uma decisão que muda a vida das pessoas. Obrigado!"

**Tela:** o README do repositório no GitHub.

---

## Por que essa solução é inovadora
- **Educa em vez de vender:** o foco é literacia financeira, não conversão.
- **Confiável por design:** anti-alucinação com camadas (busca com limiar, guardrails, prompt restritivo, contas fora do modelo).
- **Personalizada:** cruza a simulação com a renda e a entrada de cada pessoa.
- **Acessível:** roda sem chave de API e com vários provedores, então qualquer pessoa reproduz.

## Checklist de gravação
- [ ] Perfil ativado e simulação preenchida antes de gravar
- [ ] Navegador em tela cheia, zoom de 110% a 125%
- [ ] Testar as 4 perguntas da demo antes de gravar
- [ ] Manter cada bloco dentro do tempo (o total tem de ficar abaixo de 3 minutos)
