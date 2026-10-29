# Foco Leve — auditoria para a versão premium (29/10/2026)

Feita sobre `main` depois do PR #19, lendo o código (`app.py` com 2.294 linhas, `foco_leve/`, `ui.py`, `assets/tema.css`),
os testes (153 casos) e as telas no navegador (375 px e 1440 px). Prioridade: **P1** (resolver nesta etapa), **P2**
(resolver nesta etapa se couber sem risco), **P3** (próxima fase).

## 1. Navegação e organização

| # | Problema | Prioridade |
|---|---|---|
| N1 | As abas são Início, Treinos, Evolução, **Hábitos**, Perfil. Não existe um lugar do "plano": objetivo, equipamentos e grupos prioritários ficam no formulário do **Perfil**; o plano de 20 semanas e a biblioteca ficam no fim da aba **Treinos**; "Plano de exercícios" (ativar/desativar) fica no fim do **Perfil**. | P1 |
| N2 | **Funcionalidade duplicada:** o mesmo conjunto de dados (dias, tempo, nível, limitações, objetivo) é editado em 3 formulários — primeiro acesso, "Editar meus dados" no Início e Perfil. | P1 |
| N3 | **Início sobrecarregado:** capa do treino, observações, sugestões, lembrete de cópia, pontos, anéis da semana, peso, última sessão, check-in e o formulário "Editar meus dados" — rolagem longa no celular. | P1 |
| N4 | **Perfil sobrecarregado:** conta, compartilhar, instalar, dados, objetivo, avaliação de segurança, plano de exercícios, fotos offline, cópia de segurança, apagar dados e fontes. | P1 |
| N5 | Hábitos (água, sono, refeições) ocupa uma aba principal, mas é um registro secundário. | P2 |

## 2. Visual e usabilidade

| # | Problema | Prioridade |
|---|---|---|
| V1 | Não há símbolo de marca: o cabeçalho mostra só o texto "FOCO LEVE" e o ícone do app é um halter genérico. | P1 |
| V2 | Excesso de caixas com borda (19 contêineres com borda no `app.py`), o que pesa o visual. | P2 |
| V3 | Cronômetro de descanso sem "pular" nem "+15 s" (comum em apps de treino). | P1 |
| V4 | Gráficos de peso sem unidade no eixo (o valor só aparece ao tocar). | P2 |
| V5 | Barra de abas: o item ativo é só a cor do texto e do ícone; pouco destaque. | P2 |
| V6 | Tipografia dos números: tamanhos e pesos variam entre cartões. | P2 |

## 3. Persistência, concorrência e isolamento (o que já existe)

Verificado no código e coberto por testes que rodam hoje:
- **Isolamento:** uma linha por usuário no Supabase com RLS (`supabase/schema.sql`); testado num PostgreSQL 16 real
  (`tests/test_rls_postgres.py`): outro usuário não lê, não altera, não apaga e não cria em nome de outro; sem login não há acesso.
- **Concorrência:** gravação condicional por versão (CAS) com gatilho no banco; duas abas nunca gravam uma por cima da
  outra (`tests/test_integridade.py`, `tests/test_armazenamento.py`, inclusive com processos simultâneos).
- **Cache entre contas:** `sair()` apaga toda a sessão do Streamlit; testes de troca de conta não encontram dados da conta anterior.
- **Falha de rede:** `salvar()` mantém a alteração na tela, avisa "Alteração ainda não salva" e oferece "Tentar salvar agora".
- **Recuperação da sessão de treino:** a sessão em andamento fica gravada na conta (`active`); recarregar a página e
  entrar de novo continua de onde parou (testado).

Pontos encontrados:

| # | Problema | Prioridade |
|---|---|---|
| C1 | `finalizar_sessao` acrescenta a sessão sem conferir se ela já está no histórico. Hoje um duplo toque não duplica (o formulário some no primeiro), mas não há garantia no nível dos dados. | P1 |
| C2 | Ao perder conexão no meio do treino, o aviso aparece no topo; durante a sessão ele pode ficar fora da tela. | P3 |

## 4. Celular

- Sem rolagem horizontal em 375 px nas telas medidas; alvos de toque ≥ 44 px nos cartões de escolha.
- A barra de abas fixa tem 5 itens; com a troca de Hábitos por **Meu plano**, continua com 5.

## 5. O que já existe e não será reimplementado

Registro rápido de séries ("Concluir as N séries iguais"), troca de exercício, ficha do exercício, objetivos combinados,
biblioteca, gráficos de peso (diário/semanal/mensal), peso da semana, medidas, metas de carga, recordes, pontos e
figurinhas, observações automáticas determinísticas, sugestões com confirmação, relatório semanal e PDF,
instalação na tela inicial, recuperação de senha por link, cópia de segurança.

## 6. Plano desta etapa (pequenos passos revisáveis)

1. Navegação: **Início · Treino · Evolução · Meu plano · Perfil** (N1, N5). Hábitos vira uma aba dentro da Evolução.
2. **Meu plano** concentra objetivo, equipamentos, prioridades, dias, tempo, nível e limitações, o plano de 20
   semanas, a biblioteca e o plano de exercícios (N1, N2). O Início ganha um atalho para lá no lugar do formulário duplicado (N3).
3. **Perfil** fica com conta, dados pessoais, avaliação de segurança, instalar/compartilhar, cópia e fontes (N4).
4. Marca: símbolo próprio (cabeçalho, ícone do app e tela de entrada) (V1); menos bordas e números mais fortes (V2, V6);
   barra de abas com destaque no item ativo (V5); unidades nos gráficos (V4).
5. Descanso com **Pular** e **+15 s** (V3).
6. Garantia contra sessão duplicada no histórico (C1) e testes dos fluxos críticos.
