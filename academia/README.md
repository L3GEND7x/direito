# Foco Leve — Treino e Emagrecimento (Python)

Versão em Python do app Foco Leve: treinos de 3 × 15 com fotos de cada exercício, cardio de 30 a 40 min,
check-in diário, pesagens com gráfico, hábitos, relatório semanal, progressão de carga (ACSM),
meta de cardio (OMS) e calorias estimadas (Compêndio 2024).

## Instalação

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Executar

O app exige login e guarda os dados de cada conta separadamente. Ele só abre dados pessoais com um banco configurado:

- **Supabase** (o do app publicado): siga "Configurar o Supabase" abaixo e informe as credenciais em Secrets.
- **Modo local** (só para desenvolvimento no computador): SQLite em `~/.foco_leve/foco_leve.db`.

```bash
FOCO_LEVE_MODO_LOCAL=1 streamlit run app.py
```

(No Windows PowerShell: `$env:FOCO_LEVE_MODO_LOCAL="1"; streamlit run app.py`.)
Sem Supabase e sem o modo local, o app mostra só um aviso de configuração pendente.

O app abre no navegador em http://localhost:8501.

**No celular (mesma rede Wi-Fi do computador):**

```bash
FOCO_LEVE_MODO_LOCAL=1 streamlit run app.py --server.address 0.0.0.0
```

e abra no celular `http://IP-DO-COMPUTADOR:8501`.

## Plano de 20 semanas

O plano é calculado a partir do perfil (peso, altura, idade, nível, dias, tempo e limitações) e recalculado
quando esses dados mudam, sem alterar os treinos já registrados.

- 5 fases de 4 semanas: adaptação, consolidação da técnica, progressão, consolidação da rotina e manutenção.
- Exercícios variam toda semana (nenhuma das 20 semanas repete a mesma combinação em um treino).
- Todo dia de treino tem pelo menos 30 min de cardio; a sessão é planejada para o tempo máximo do perfil (90 min por padrão),
  com aquecimento, musculação, cardio e volta à calma. Se faltar tempo, saem primeiro os exercícios isolados.
- Quanto mais longe da meta, mais minutos de cardio (dentro da faixa da OMS).
- Com IMC alto, as fases 1 e 2 usam cardio de baixo impacto e evitam exercícios no chão ou em uma perna só.
- Limitações escritas no perfil (joelho, ombro, lombar, quadril, tornozelo, punho) tiram do plano os exercícios que sobrecarregam a região.
- A semana só avança com pelo menos 60% dos treinos feitos e sem dor, sinais de alerta ou recuperação ruim.
- No Início dá para editar os dados e recalcular o plano; em Treinos, ver as 20 semanas e editar os exercícios de um treino.

O plano não substitui avaliação médica nem a orientação do profissional de educação física.

## Visual

Interface escura inspirada em apps nativos de saúde: preto profundo, superfícies grafite, um único vermelho de destaque,
tipografia do sistema (SF Pro no iPhone e no Mac; Inter, do Google Fonts, nos demais aparelhos), barra de abas fixa no rodapé
com ícones, anéis de progresso, linha do tempo das 20 semanas e gráficos com os dados registrados.
O tema fica em `assets/tema.css` (variáveis de cor, tipografia, espaçamento, raios e sombras) e os componentes em `ui.py`.
Respeita a preferência do sistema por movimento reduzido. Sem internet, a fonte cai para a do sistema e o resto continua igual.

## Contas e isolamento dos dados

- Cadastro, login, saída e recuperação de senha. Com Supabase, a senha é tratada só pelo Supabase Auth; no modo
  local fica apenas um resumo PBKDF2-SHA256 com sal (nunca a senha).
- A identidade vem do token emitido pelo servidor de autenticação e guardado na sessão do Streamlit no servidor;
  nada na URL ou no navegador escolhe de quem são os dados. A sessão é reconfirmada no servidor a cada 5 minutos.
- No Supabase, todo o estado pessoal da conta (perfil, avaliação, pesagens, plano e treinos personalizados, sessão
  em andamento, treinos concluídos, metas, preferências, hábitos e check-ins) fica numa linha da tabela
  `foco_leve_estado` cujo dono é `auth.uid()`. As políticas de Row Level Security de `supabase/schema.sql` impedem,
  no próprio Postgres, que uma conta leia, crie, altere ou apague a linha de outra.
- O único recurso compartilhado entre sessões (`st.cache_resource`) é o cliente do banco, sem tokens nem dados.
- Sair da conta limpa toda a sessão do navegador antes de mostrar o login.
- O app não recebe fotos nem arquivos pessoais (as fotos dos exercícios são públicas).

Cada gravação aumenta um número de versão: se o app estiver aberto em duas abas ou aparelhos, a aba desatualizada
recarrega os dados antes de mostrar a tela e nunca grava por cima do que a outra salvou.
Em Perfil → Cópia de segurança é possível baixar e restaurar um `.json` da própria conta (com confirmação, porque
substitui os registros atuais); a cópia não leva e-mail, identificador nem token.

O dia de "hoje" segue o fuso escolhido no Perfil (padrão: Brasília), porque o servidor do Streamlit Cloud roda em UTC.

## Configurar o Supabase

1. Crie um projeto em https://supabase.com (plano gratuito serve).
2. **SQL Editor → New query**: cole todo o conteúdo de `supabase/schema.sql` e clique em **Run**. Pode rodar de novo
   sem perder dados.
3. **Authentication → Sign In / Providers → Email**: deixe o login por e-mail ativo. Com "Confirm email" ligado, a
   pessoa confirma o cadastro pelo link do e-mail antes do primeiro login.
4. **Authentication → URL Configuration → Site URL**: o link público do app no Streamlit.
5. "Esqueci a senha" funciona com o e-mail padrão do Supabase: o link do e-mail volta para o app, que troca o código
   do link por uma sessão (fluxo PKCE, com o verificador guardado só no servidor) e pede a nova senha. O link vale por
   1 hora e só uma vez; se o app reiniciar nesse meio-tempo, basta pedir outro. Se o modelo **Reset Password** puder
   ser editado (exige SMTP próprio em alguns planos), dá para incluir também `{{ .Token }}`: o app aceita o código
   numérico em "Recebi um código numérico no e-mail".
6. **Project Settings → API Keys / Data API**: copie a *Project URL* e a chave **pública** (anon ou publishable).
7. No Streamlit Community Cloud: app → **Settings → Secrets**, cole o modelo de `.streamlit/secrets.toml.example`
   com a URL, a chave pública e o `site_url` (o link do app) e salve. Vale na próxima recarga da página. Se algo
   estiver errado, o aviso do app diz o quê (erro de formato e a linha, seção ou campo faltando, chave secreta),
   sem mostrar nenhum valor.

O envio de e-mails do Supabase gratuito tem limite baixo de mensagens por hora; para uso com muitas pessoas,
configure um SMTP próprio em Authentication → SMTP Settings.

### Testar com duas contas

1. Numa janela normal, crie a conta A, faça o primeiro acesso e registre um peso e um hábito.
2. Numa janela anônima (ou outro aparelho), crie a conta B: ela deve começar vazia.
3. Registre um peso diferente em B. Volte à janela de A e recarregue: A continua só com os próprios registros.
4. Em B, use Perfil → Sair da conta e entre como A: aparecem só os dados de A.
5. No Supabase, **Table Editor → foco_leve_estado** deve mostrar duas linhas, uma por `user_id`.

## Dados da versão anterior (sem contas)

As versões anteriores guardavam um único registro compartilhado por todos os visitantes. Não dá para saber de quem
ele é, então o app novo não o mostra nem o atribui a ninguém, e nunca o apaga. Antes de publicar a versão com contas,
abra o app atual e baixe a cópia em Perfil → Cópia de segurança. Depois, quem for dono dos registros entra na
própria conta e usa **Restaurar**. Num servidor próprio com o SQLite antigo, `python migrar_legado.py listar |
exportar | atribuir` faz o mesmo com backup prévio (veja a ajuda do script).

## Personal IA (Foco Leve AI — Personal Trainer)

Aba **Personal IA**: conversa em português com um assistente de treino que usa os dados da sua conta (perfil,
avaliação, plano, treinos, pesagens e hábitos), analisa fotos (JPEG, PNG, WebP), guarda o histórico e propõe ajustes.

- **Provedor:** Claude, da Anthropic, pelo SDK oficial `anthropic` (texto e imagem). Modelo padrão `claude-opus-5-5`,
  com raciocínio adaptativo, esforço `medium` e *fallback* do lado do servidor quando um classificador de segurança
  recusa o pedido. Sem chave configurada, a aba avisa e não envia nada — não há resposta simulada.
- **Privacidade:** conversas, mensagens e fotos ficam nas tabelas de `supabase/personal_ia.sql`, com RLS: cada conta só
  lê, cria, altera ou exclui o que é seu, e não consegue escrever na conversa de outra pessoa. As fotos são regravadas
  pelo app como JPEG sem metadados (EXIF/GPS). Para a IA vão só os dados necessários à pergunta, sem nome, e-mail nem
  identificadores. Sair da conta limpa toda a tela.
- **Segurança:** relatos como dor no peito, falta de ar ou desmaio recebem uma resposta fixa do app (procurar o SAMU,
  192) sem passar pela IA; dor forte, inchaço, perda de força ou lesão geram um aviso fixo e uma instrução obrigatória
  para a resposta. A IA não diagnostica, não prescreve remédios nem dietas extremas.
- **Mudanças no plano:** a IA só *propõe* (treino da semana, tempo, dias, nível, limitação nova, descanso hoje). O app
  mostra um cartão e grava apenas quando você toca em **Aplicar ao meu plano**, validando de novo os exercícios pelas
  mesmas regras de segurança do plano. Peso, metas e registros nunca são alterados pela IA.
- **Custos e limites:** por conta, 40 mensagens e 15 fotos a cada 24 h (configurável); do histórico vão o resumo da
  conversa e as 8 últimas mensagens em texto; o prompt de sistema fica em cache.

### Configurar o Personal IA

1. Crie uma chave em https://console.anthropic.com → **API Keys** (exige conta com créditos ou cartão).
2. No Supabase, rode `supabase/personal_ia.sql` no SQL Editor (depois de `schema.sql`).
3. Em **Settings → Secrets** do Streamlit Cloud, acrescente:

```toml
[ia]
anthropic_api_key = "COLE-AQUI-A-CHAVE"   # obrigatório; nunca no repositório
# opcionais (valores padrão):
# modelo = "claude-opus-5-5"
# esforco = "medium"                       # low | medium | high | xhigh | max
# max_tokens = 16000
# timeout_s = 120
# max_foto_mb = 8
# max_fotos_por_mensagem = 3
# limite_mensagens_dia = 40
# limite_fotos_dia = 15
# janela_mensagens = 8
# fallback = true
```

A chave também pode vir da variável de ambiente `ANTHROPIC_API_KEY`. Ela só é usada no servidor.

**Custo de referência (Claude Opus 5.5, outubro de 2026):** US$ 4 por milhão de tokens de entrada e US$ 20 por milhão
de saída (leitura de cache: US$ 0,20). Uma pergunta típica (~3 mil tokens de entrada com contexto e ~800 de saída,
incluindo raciocínio) fica perto de **US$ 0,03**; cada foto acrescenta ~1,5 mil tokens de entrada (≈ US$ 0,006). Com o
limite padrão, o teto teórico por conta é de ~40 perguntas por dia. Para baratear, `esforco = "low"` ou outro modelo
(ex.: `modelo = "claude-sonnet-5-5"`, US$ 2/US$ 10) — escolha sua, depois de comparar a qualidade. Confira os preços
atuais em https://www.anthropic.com/pricing. O plano gratuito do Supabase tem 500 MB de banco: cada foto ocupa ~0,2 a
0,4 MB.

### Testar o Personal IA com duas contas

1. Conta A (janela normal): abra **Personal IA**, envie "Monte meu treino de hoje." e uma foto de um aparelho.
2. Conta B (janela anônima): a aba começa sem conversas; envie outra pergunta.
3. Em A, recarregue: só as conversas de A aparecem. Em **Minhas conversas**, exclua uma e confirme.
4. Peça em A "Adapte meu treino às limitações que informei": se vier um cartão de proposta, confira que o plano em
   Treinos só muda depois de **Aplicar ao meu plano**.
5. No Supabase, **Table Editor → foco_leve_ia_conversas**: cada linha tem o `user_id` da conta dona.

## Estrutura

```
app.py                     interface (5 abas: Início, Treinos, Evolução, Hábitos, Perfil)
ui.py                      componentes visuais (anéis, semana, linha do tempo, estados vazios)
assets/tema.css            sistema de design (variáveis, componentes, barra inferior)
foco_leve/dados.py         31 exercícios, 8 treinos, alternativas, intensidades de cardio, fontes
foco_leve/regras.py        segurança, agenda, sessão, progressão, calorias, relatório
foco_leve/plano.py         plano personalizado de 20 semanas
foco_leve/evolucao.py      números da evolução calculados só com dados registrados
foco_leve/armazenamento.py contas, Supabase (REST + RLS), SQLite local e importação de cópias
supabase/schema.sql        tabela, permissões e políticas de Row Level Security
migrar_legado.py           decisão sobre o registro da versão sem contas (listar, exportar, atribuir)
personal_ai.py             tela do Personal IA (conversa, fotos, histórico, propostas com confirmação)
foco_leve/ia_service.py    comunicação com o modelo (SDK anthropic, streaming, erros, resumo)
foco_leve/ia_context.py    contexto da conta para cada pergunta (só o necessário, com a origem de cada dado)
foco_leve/ia_storage.py    conversas, mensagens e fotos por usuário (Supabase com RLS ou SQLite local)
foco_leve/ia_vision.py     validação e regravação das fotos (formato, tamanho, sem metadados)
foco_leve/ia_safety.py     sinais de alerta, validação de mensagens e das propostas da IA
supabase/personal_ia.sql   tabelas e políticas RLS do Personal IA
tests/                     testes automáticos (pytest)
```

## Testes

```bash
python -m pytest -q
```

`tests/test_rls_postgres.py` sobe um PostgreSQL temporário (precisa dos binários do PostgreSQL instalados; sem eles
o teste é pulado), recria o mínimo do Supabase (papéis `anon`/`authenticated`, `auth.uid()`) e aplica o
`supabase/schema.sql` e o `supabase/personal_ia.sql` reais para tentar acessos cruzados entre contas.
`tests/ia_falso.py` é um servidor local que **simula** a API da Anthropic: os testes do Personal IA usam o SDK
oficial apontado para ele (streaming, ferramenta, recusa, erros 401/404/429/529, queda de conexão). Nenhum teste chama
a API real; isso exige uma chave e foi deixado para o teste manual descrito acima.

## Fontes

- OMS (2020): 150 a 300 min/semana de atividade aeróbica moderada.
- ACSM, Progression Models in Resistance Training: aumentar 2 a 10% ao superar a meta em 1 a 2 repetições.
- 2024 Adult Compendium of Physical Activities: METs usados nas calorias estimadas.
- Fotos: Free Exercise DB (domínio público, Unlicense) — https://github.com/yuhonas/free-exercise-db

Os valores de calorias são estimativas. O app não substitui avaliação médica nem a orientação do profissional de educação física.
