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

```bash
streamlit run app.py
```

O app abre no navegador em http://localhost:8501.

**No celular (mesma rede Wi-Fi do computador):**

```bash
streamlit run app.py --server.address 0.0.0.0
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

Tema vermelho e preto com fontes Teko (títulos) e Poppins (texto), carregadas do Google Fonts.
Sem internet, o app usa a fonte padrão do sistema; as cores e o layout continuam iguais.

## Publicar online (Streamlit Community Cloud)

1. Entre em https://share.streamlit.io com a conta do GitHub.
2. **Create app** → repositório `L3GEND7x/direito`, branch `main`, arquivo principal `academia/app.py`.
3. Clique em **Deploy**. O app funciona do Python 3.12 ao 3.14 (testado nos dois extremos).

O tema vermelho e preto online vem de `.streamlit/config.toml` na raiz do repositório;
a cópia em `academia/.streamlit/` vale quando o app roda no computador, de dentro desta pasta.

Atenção: online, o banco SQLite fica no servidor e é apagado quando o app reinicia ou é atualizado.
Baixe a cópia de segurança em Perfil com frequência. O app não tem login: quem tiver o link vê e altera os dados.

## Onde ficam os dados

Em um banco SQLite em `~/.foco_leve/foco_leve.db` (mude com a variável `FOCO_LEVE_DB`).
Em Perfil → Cópia de segurança é possível baixar e restaurar um `.json`, inclusive a cópia exportada da versão web.

## Estrutura

```
app.py                     interface (5 abas: Início, Treinos, Evolução, Hábitos, Perfil)
foco_leve/dados.py         31 exercícios, 8 treinos, alternativas, intensidades de cardio, fontes
foco_leve/regras.py        segurança, agenda, sessão, progressão, calorias, relatório
foco_leve/plano.py         plano personalizado de 20 semanas
foco_leve/armazenamento.py SQLite e importação de cópias
tests/                     testes automáticos (pytest)
```

## Testes

```bash
python -m pytest -q
```

## Fontes

- OMS (2020): 150 a 300 min/semana de atividade aeróbica moderada.
- ACSM, Progression Models in Resistance Training: aumentar 2 a 10% ao superar a meta em 1 a 2 repetições.
- 2024 Adult Compendium of Physical Activities: METs usados nas calorias estimadas.
- Fotos: Free Exercise DB (domínio público, Unlicense) — https://github.com/yuhonas/free-exercise-db

Os valores de calorias são estimativas. O app não substitui avaliação médica nem a orientação do profissional de educação física.
