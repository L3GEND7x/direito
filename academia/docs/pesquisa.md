# Foco Leve — base científica, exercícios e acompanhamento

Pesquisa feita em 29/10/2026 para a atualização "objetivos, biblioteca de exercícios e acompanhamento automático".
Sem chatbot, sem IA e sem APIs externas novas: tudo é calculado no próprio app, a partir dos registros de cada conta.

**Como foi verificada.** Os sites dos periódicos (doi.org, PubMed, PMC, BMJ, Frontiers, ACSM, OMS) estão bloqueados
na rede deste ambiente de desenvolvimento. Os dados de cada estudo (título, autores, ano, periódico, DOI, conclusões)
foram conferidos por busca na web, em mais de uma fonte quando possível. Os links ficam no app como texto de
referência, mas **não foram abertos daqui**: confira-os uma vez num navegador comum antes de divulgar o app.
Onde um dado não foi confirmado, ele foi omitido (por exemplo, volume e páginas de Kikuchi & Nakazato).

---

## 1. Onde fica cada funcionalidade (antes desta atualização)

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Interface Streamlit: login, primeiro acesso, abas Início / Treinos / Evolução / Hábitos / Perfil, sessão de treino, gráficos |
| `ui.py`, `assets/tema.css` | Tema preto e vermelho, componentes HTML (capa, cartões, anéis), ajustes de página |
| `foco_leve/dados.py` | Catálogo: exercícios (instruções, cuidados, prescrição), modelos de treino por "vagas", fases das 20 semanas, agendas, fotos |
| `foco_leve/plano.py` | Gerador do plano: nível, fase, IMC/baixo impacto, limitações, rodízio por conta, cardio, ajuste ao tempo máximo |
| `foco_leve/regras.py` | Estado padrão, segurança (sintomas, alertas), sessão, progressão de carga, energia, relatório |
| `foco_leve/evolucao.py` | Números da Evolução (frequência, cardio, cargas, peso) |
| `foco_leve/armazenamento.py`, `supabase/schema.sql` | Contas e dados por usuário (SQLite local ou Supabase com RLS) |

**Novos nesta atualização:** `foco_leve/objetivos.py` (efeito de cada objetivo no plano), `foco_leve/biblioteca.py`
(grupo, equipamento, dificuldade e fontes de cada exercício), `foco_leve/monitoramento.py` (observações automáticas),
`tests/test_objetivos.py`.

---

## 2. Projetos de código aberto avaliados

Nenhum código foi copiado. O que se aproveitou foram ideias de organização (taxonomia de grupos musculares,
equipamento por exercício, histórico por grupo). As fotos já vinham do Free Exercise DB, de domínio público.

| Projeto | O que é | Licença | Atividade | Aproveitamento possível |
|---|---|---|---|---|
| [wger-project/wger](https://github.com/wger-project/wger) | Gerenciador de treinos e dieta (Django), com API e base colaborativa de exercícios | Código **AGPL-3.0**; dados dos exercícios em **Creative Commons por exercício** (historicamente CC-BY-SA); docs CC-BY-SA-4.0 | Ativo, projeto grande e documentado | Referência de modelo de dados (músculos primários/secundários, equipamento). Copiar código obrigaria o Foco Leve a virar AGPL; copiar dados exige atribuição e compartilhamento pela mesma licença. **Não usado diretamente.** |
| [skulptapp/skulpt](https://github.com/skulptapp/skulpt) | Registro de treinos local-first (TypeScript; iOS, Android, Watch) | **GPL-3.0** (arquivo LICENSE conferido) | Ativo em 2026, projeto pequeno | Ideias de registro rápido de séries. GPL impede copiar código para um app sob outra licença. **Não usado.** |
| [LibreFitOrg/LibreFit](https://github.com/LibreFitOrg/LibreFit) | App Android de treino (F-Droid) | **GPL-3.0-or-later** | Ativo (v0.4.1, jul/2026) | Ideias de interface móvel. **Não usado.** |
| [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db) | Base de 800+ exercícios em JSON com fotos | **Unlicense** (domínio público) | Mantido | **Já usado** para as fotos (início e fim do movimento). As 11 fotos novas foram conferidas uma a uma (endereço respondendo e movimento correto). Exercícios sem foto correspondente (ponte de glúteo sem barra, caminhada ao ar livre) ficaram sem foto. |
| [wrkout/exercises.json](https://github.com/wrkout/exercises.json) | Base de exercícios em JSON | Domínio público (declarado no README) | Pouca atividade | Origem do Free Exercise DB. Não necessário. |
| [exercemus/exercises](https://github.com/exercemus/exercises) | Lista de exercícios compilada | Código **MIT**, mas a lista **mistura dados do wger** (CC-BY-SA) | — | **Risco de licença:** o MIT do repositório não cobre os dados vindos do wger. Não usado. |
| [Snouzy/workout-cool](https://github.com/Snouzy/workout-cool) | Plataforma web de treinos (Next.js) | **MIT** | Ativo | Ideias de biblioteca por músculo. Não usado. |

**Segurança e privacidade:** nenhum desses projetos foi incluído como dependência; o app continua sem enviar
dados pessoais a serviços externos (as fotos são públicas e carregadas do GitHub, sem dados da conta).

---

## 3. Referências científicas

Tipo de evidência, do mais forte ao mais fraco: diretriz/posicionamento baseado em revisões > revisão sistemática
com meta-análise > ensaio clínico randomizado > estudo de ativação (EMG) > opinião. Conteúdo de influenciadores e
"melhor exercício" de redes sociais **não** foi usado como base.

### 3.1 ACSM (2026) — posicionamento sobre treinamento resistido
- **Título:** Resistance Training Prescription for Muscle Function, Hypertrophy, and Physical Performance in Healthy Adults: An Overview of Reviews (Position Stand)
- **Autoria:** American College of Sports Medicine · **Ano:** 2026 · Med Sci Sports Exerc 58(3):512–545
- **Link:** [infográfico do ACSM](https://acsm.org/wp-content/uploads/2026/03/Resistance-Training-Position-Stand-infographic.pdf) · [nota da McMaster](https://news.mcmaster.ca/?p=30899)
- **Tipo:** revisão de revisões (137 revisões sistemáticas, mais de 30 mil participantes)
- **Conclusões usadas:** qualquer treino resistido é melhor que nenhum; treinar os grandes grupos musculares pelo menos 2 dias por semana; volume, intensidade e frequência podem variar conforme a preferência, com progressão gradual.
- **Limitações:** o PMID citado no pedido (41843416) não pôde ser confirmado daqui; as conclusões vêm do resumo, do infográfico e da divulgação oficial.
- **No app:** cada grupo prioritário entra em pelo menos 2 treinos por semana; com 3 dias e foco muscular ou treino completo, a agenda vira corpo inteiro 3×.

### 3.2 Exercício resistido durante a perda de peso (2025)
- **Título:** Effect of resistance exercise on body composition, muscle strength and cardiometabolic health during dietary weight loss in people living with overweight or obesity: a systematic review and meta-analysis
- **Ano:** 2025 · BMJ Open Sport & Exercise Medicine 11(3):e002363 · DOI 10.1136/bmjsem-2024-002363 · [PMC12406911](https://pmc.ncbi.nlm.nih.gov/articles/PMC12406911/) (PMID 40909191)
- **Autoria:** lista completa não confirmada daqui (estudo 1 da tese de A. Binmahfoz, Univ. de Glasgow).
- **Tipo:** revisão sistemática e meta-análise de 25 ensaios randomizados
- **Conclusões:** somar musculação à dieta **não mudou a perda de peso total**; **preservou massa magra** (certeza moderada); **aumentou a perda de gordura** (certeza alta); melhorou força (certeza baixa); sem efeito em outros marcadores cardiometabólicos.
- **Limitações:** estudos heterogêneos; adultos de 18 a 65 anos; certeza baixa para força.
- **No app:** no objetivo Emagrecimento, a musculação continua em todos os treinos e o texto explica balanço de energia, sem queima localizada e sem promessa de quilos.

### 3.3 Currier et al. (2023) — prescrição para força e hipertrofia
- **Título:** Resistance training prescription for muscle strength and hypertrophy in healthy adults: a systematic review and Bayesian network meta-analysis
- **Autores:** Currier BS et al. · **Ano:** 2023 · Br J Sports Med 57:1211–1220 · DOI 10.1136/bjsports-2023-106807 · [PMC10579494](https://pmc.ncbi.nlm.nih.gov/articles/PMC10579494/) (PMID 37414459)
- **Tipo:** meta-análise em rede (178 estudos de força, 119 de hipertrofia)
- **Conclusões:** todas as prescrições foram melhores que não treinar; cargas altas (>80% de 1RM) maximizaram a força; para hipertrofia as prescrições foram **comparáveis** (a mais bem ranqueada: carga alta, várias séries, 2× por semana).
- **Limitações:** estudos curtos, maioria com pessoas jovens e saudáveis.
- **No app:** o app mantém 15 repetições (mais seguro para iniciantes e pessoas com obesidade) e progride carga pela regra existente; hipertrofia não exige repetições baixas.

### 3.4 Volume e frequência
- **Schoenfeld, Ogborn & Krieger (2017).** Dose-response relationship between weekly resistance training volume and increases in muscle mass. J Sports Sci 35:1073–1082. DOI 10.1080/02640414.2016.1210197. Meta-análise: mais séries semanais por grupo → mais hipertrofia, com dados até cerca de 10+ séries/semana. **Limitações:** maioria de pessoas sem treino e estudos curtos; há estudos que não acharam dose-resposta.
- **Pelland et al. (2026, Sports Med 56(2):481–505; preprint SportRxiv 2024).** Meta-regressão com 67 estudos: volume com retorno decrescente; frequência quase sem efeito na hipertrofia quando o volume é igual, com efeito positivo na força.
- **Schoenfeld, Grgic & Krieger (2019), J Sports Sci.** Com volume igual, a frequência semanal não mudou a hipertrofia (25 estudos).
- **Refalo et al. (2023), Sports Med 53(3):649–665** e **Robinson et al. (2024), Sports Med 54(9):2209–2231:** treinar até a falha não é necessário; séries próximas da falha bastam.
- **No app:** foco muscular (hipertrofia, glúteos, peitoral) acrescenta **1 exercício do grupo prioritário** por treino e **4 séries nos compostos** depois da adaptação (nível intermediário ou avançado). Iniciantes não ganham séries extras. Esforço continua em "6 a 7 de 10".

### 3.5 Glúteos
- **Plotkin et al. (2023).** Hip thrust and back squat training elicit similar gluteus muscle hypertrophy and transfer similarly to the deadlift. Front Physiol 14:1279170. DOI 10.3389/fphys.2023.1279170 · [PMC10593473](https://pmc.ncbi.nlm.nih.gov/articles/PMC10593473/). Ensaio randomizado, 9 semanas, universitários **sem treino** (hip thrust n=18, agachamento n=16), ressonância magnética: **hipertrofia de glúteos semelhante**; agachamento aumentou mais a coxa (quadríceps, adutores). Maior EMG do hip thrust **não previu** mais hipertrofia.
- **Barbalho et al. (2020).** Int J Sports Med 41(5):306–310. DOI 10.1055/a-1082-1126. Mulheres **treinadas**, 12 semanas: agachamento aumentou mais a espessura de glúteos e quadríceps. **Limitação:** amostra pequena e ultrassom.
- **Leitura:** os dois estudos discordam em detalhes e usam populações diferentes; **não existe "o melhor exercício para glúteos"**. Por isso o app faz rodízio entre hip thrust, extensão de quadril no cabo, afundo reverso, ponte, step-up e abdução, e mantém agachamento/leg press nos treinos de pernas.

### 3.6 Peitoral
- **Kikuchi & Nakazato (2017).** J Exerc Sci Fit, DOI 10.1016/j.jesf.2017.06.003. 18 homens jovens, 8 semanas: flexão de braços com carga equivalente e supino (40% 1RM) deram ganhos semelhantes de peitoral e força. **Limitação:** amostra muito pequena; volume e páginas não confirmados.
- **Chaves et al. (2020).** Effects of Horizontal and Incline Bench Press on Neuromuscular Adaptations in Untrained Young Men. Int J Exerc Sci 13(6):859–872 · [PMC7449336](https://pmc.ncbi.nlm.nih.gov/articles/PMC7449336/). 47 homens sem treino: força semelhante; o inclinado aumentou mais a porção superior do peitoral. **Limitação:** só homens iniciantes.
- **No app:** rodízio entre supino inclinado, flexões, crossover, supino com halteres e chest press, em 2 treinos por semana.

### 3.7 Cardio e saúde
- **Bull et al. (2020).** WHO 2020 guidelines on physical activity and sedentary behaviour. Br J Sports Med 54:1451–1462. DOI 10.1136/bjsports-2020-102955. Adultos: 150–300 min/semana de atividade moderada (ou 75–150 vigorosa) e fortalecimento muscular dos grandes grupos em 2 ou mais dias.
  **Limitação de verificação:** a redação exata para adultos ("moderada ou maior intensidade, 2 ou mais dias") veio de fontes secundárias; a página da OMS não abriu daqui.
- **No app:** emagrecimento mantém o alvo de 150 a 250 min conforme a distância da meta; condicionamento sobe para pelo menos 200 min; os demais objetivos ficam em 150 min (mínimo da OMS), com 20 a 30 min por sessão.

### Evidência × opinião
- **Evidência:** itens 3.1 a 3.7.
- **Escolhas de projeto (não são evidência):** manter 15 repetições, limitar a 2 grupos prioritários (tempo da sessão), 4 séries nos compostos só depois da adaptação, regras de dificuldade por nível.

---

## 4. O que foi implementado

1. **Objetivos em cartões** (Perfil, primeiro acesso e "Editar meus dados"): Emagrecimento, Hipertrofia, Glúteos, Peitoral, Treino completo, Condicionamento — um ou vários (objetivo combinado). Também **equipamentos disponíveis** e **grupos prioritários** (até 2).
2. **Plano conforme o objetivo** (`objetivos.py` + `plano.py`): vagas prioritárias 2×/semana, séries extras no foco muscular, alvo de cardio por objetivo, agenda de corpo inteiro com 3 dias, alternativas sem máquinas (halteres, barra, peso do corpo, caminhada ao ar livre). Contas antigas sem esses campos recebem exatamente o plano de antes (testado).
3. **Biblioteca de exercícios** na aba Treinos, por grupo muscular: grupo principal e secundários, músculos, objetivos, equipamento, dificuldade, prescrição base, passos, cuidados, alternativas, fontes e, quando for o caso, **o motivo de estar fora do plano** daquela conta. 13 exercícios novos (hip thrust, extensão de quadril no cabo, ponte, flexões, supino inclinado com halteres, agachamento livre, terra romeno, afundo reverso, step-up, agachamento com peso do corpo, remada unilateral, caminhada ao ar livre).
4. **Acompanhamento automático** (`monitoramento.py`), sem chatbot: planejado × concluído, queda ou alta de frequência, dias sem treinar, séries concluídas, aumento/redução de carga, carga parada há 4 sessões, séries dos grupos prioritários, média de peso de 2 semanas, sessões interrompidas e dor registrada. Aparece em Início (3), Treinos (2) e Evolução (6). **Nada muda o plano sozinho**; sugestões só indicam onde a pessoa pode ajustar.
5. **Evolução:** séries por grupo muscular (28 dias) e histórico semanal por grupo. Corrigida a linha de referência dos gráficos (150 min de cardio e meta de peso), que aparecia como linhas verticais.
6. **Segurança mantida:** sintomas, limitações por região, exercícios proibidos (agora também pelos apelidos dos novos, ex.: "hip thrust", "flexão"), baixo impacto por IMC e lesão em recuperação continuam valendo antes de qualquer regra de objetivo. Dor registrada gera alerta sem diagnóstico, orientando suspender e procurar um profissional.

## 5. Testes

`tests/test_objetivos.py` (58 casos) e um teste de interface novo em `tests/test_app.py`:
cada objetivo e 5 combinações × 3 níveis × 2–5 dias × 3 fases (sem repetição, sem exercício bloqueado, dentro do tempo,
iniciante sem técnica avançada); glúteos e peitoral 2×/semana; hipertrofia com 4 séries e cardio ≤ 30 min; equipamento
(só halteres/corpo, só corpo, só barra, só máquinas); limitações e sintomas com prioridades; exercícios proibidos por
nome; biblioteca cobrindo o catálogo e fontes bem formadas; observações (sem dados, cargas, dor sem diagnóstico, queda
de frequência, peso só com pesagens suficientes, nenhuma alteração do estado); persistência e isolamento de duas
contas no banco após reabrir. A suíte inteira (incluindo RLS num PostgreSQL real) passa em Python 3.12 e 3.14.
Verificação visual em 375 e 1440 px: sem rolagem horizontal, sem erros de JavaScript, cartões com 44 px de altura.

## 6. Limitações e o que depende de configuração

- **Links das referências:** não abertos deste ambiente (rede bloqueada); confira num navegador.
- **Supabase:** os campos novos ficam no mesmo JSON por usuário (`dados`), já coberto pelo RLS. **Não é preciso rodar SQL novo.**
- **Sem vídeos:** nenhuma fonte de vídeo foi validada; só fotos do Free Exercise DB conferidas.
- **Grupo muscular por exercício** conta só o grupo principal nas séries semanais (os secundários aparecem na biblioteca).
- As observações dependem do que a pessoa registra: sem carga anotada, não há comparação de carga.
