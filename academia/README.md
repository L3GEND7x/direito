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
5. **Authentication → Email Templates → Reset Password**: inclua o código no texto, por exemplo
   `Seu código para trocar a senha do Foco Leve: {{ .Token }}`. O app pede esse código (não usa o link).
6. **Project Settings → API Keys / Data API**: copie a *Project URL* e a chave **pública** (anon ou publishable).
7. No Streamlit Community Cloud: app → **Settings → Secrets**, cole o modelo de `.streamlit/secrets.toml.example`
   com esses dois valores e salve. O app reinicia sozinho.

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
tests/                     testes automáticos (pytest)
```

## Testes

```bash
python -m pytest -q
```

`tests/test_rls_postgres.py` sobe um PostgreSQL temporário (precisa dos binários do PostgreSQL instalados; sem eles
o teste é pulado), recria o mínimo do Supabase (papéis `anon`/`authenticated`, `auth.uid()`) e aplica o
`supabase/schema.sql` real para tentar acessos cruzados entre contas.

## Fontes

- OMS (2020): 150 a 300 min/semana de atividade aeróbica moderada.
- ACSM, Progression Models in Resistance Training: aumentar 2 a 10% ao superar a meta em 1 a 2 repetições.
- 2024 Adult Compendium of Physical Activities: METs usados nas calorias estimadas.
- Fotos: Free Exercise DB (domínio público, Unlicense) — https://github.com/yuhonas/free-exercise-db

Os valores de calorias são estimativas. O app não substitui avaliação médica nem a orientação do profissional de educação física.
