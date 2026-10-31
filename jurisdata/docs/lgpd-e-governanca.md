# LGPD e governança — o que o sistema faz e o que o escritório precisa fazer

O software aplica controles técnicos. A conformidade com a LGPD (Lei nº 13.709/2018) também depende de
decisões e documentos do escritório, que não podem ser resolvidos só com código. Esta página separa as
duas coisas.

## 1. Controles implementados

| Princípio / exigência | Como o JurisData aplica |
| --- | --- |
| Finalidade e adequação (art. 6º, I e II) | Consulta só com processo/demanda ativa, finalidade, justificativa (mín. 30 caracteres) e declaração |
| Necessidade (art. 6º, III) | Limite de consultas em 24 h; CPF mascarado por padrão; versão integral só para advogado e registrada à parte |
| Base legal (art. 7º) | Escolhida e gravada **antes** da execução; consentimento não é o padrão |
| Segurança (arts. 46 a 49) | MFA obrigatório, Argon2, criptografia em repouso (Fernet), TLS obrigatório em produção, CSP, CSRF, bloqueio de tentativas, sessões com expiração |
| Prestação de contas (art. 6º, X) | Trilha de auditoria encadeada por hash: solicitação, aprovação, execução, falha, visualização, exportação, login, alterações de usuários |
| Eliminação (arts. 15 e 16) | Expurgo automático do conteúdo e do documento em claro após o prazo de retenção |
| Controle de acesso | Login individual, perfis, aprovação de advogado para assistentes, revogação imediata ao desativar usuário |
| Transparência interna | Termo de responsabilidade aceito e registrado no 1º acesso |

## 2. Decisões que cabem ao escritório

Itens marcados [PREENCHER] precisam de decisão do responsável pelo escritório ou do encarregado.

| Decisão | Situação |
| --- | --- |
| Encarregado (DPO) ou dispensa de agente de pequeno porte (Res. CD/ANPD nº 2/2022) | [PREENCHER] |
| Papel do escritório em cada tratamento (controlador, operador) e do SERPRO | [PREENCHER] — ver Guia de agentes de tratamento da ANPD |
| Prazo de retenção por finalidade | Padrão técnico: 365 dias. [PREENCHER] conforme a política do escritório e prazos prescricionais aplicáveis |
| Limite diário por usuário | Padrão: 30. [PREENCHER] |
| Exigir aprovação para assistentes | Padrão: sim |
| Provedor de hospedagem e região | Ainda não definido. Preferência: região no Brasil; se houver transferência internacional, avaliar art. 33 |
| Necessidade de Relatório de Impacto (RIPD) | [PREENCHER] — avaliar diante do volume e da natureza das consultas |

## 3. Matriz de bases legais (modelo)

| Finalidade | Base legal mais provável | Observação |
| --- | --- | --- |
| Qualificação de parte em processo | Art. 7º, VI | Vincular ao processo |
| Subsídio para citação/intimação | Art. 7º, VI | Idem |
| Pesquisa patrimonial em execução | Art. 7º, VI | Preferir pedido ao juízo (SISBAJUD/RENAJUD) quando a medida depender de ordem judicial |
| Instrução de defesa | Art. 7º, VI | Cuidado redobrado com terceiros não partes |
| Due diligence contratual | Art. 7º, V ou IX | IX exige teste de legítimo interesse documentado (art. 10) |
| Verificação para concessão de crédito | Art. 7º, X | Raro em escritório; avaliar caso a caso |

A matriz é ponto de partida. A escolha final é do advogado responsável, diante do caso concreto.

## 4. Documentos a produzir (fora do software)

- [ ] Política de privacidade e canal de atendimento ao titular
- [ ] Termos de uso interno (base: termo exibido no 1º acesso, `app/rotas_auth.py`)
- [ ] Registro das operações de tratamento (ROPA) — o histórico de consultas e a auditoria fornecem os dados
- [ ] Política de retenção e descarte
- [ ] Procedimento de resposta a incidentes e comunicação à ANPD e aos titulares
- [ ] Contratos com operadores (hospedagem, backup, SERPRO)
- [ ] Termo de responsabilidade assinado por funcionário (além do aceite eletrônico)
- [ ] Procedimento de desligamento: desativar usuário no mesmo dia (revoga sessões na hora)

## 5. Riscos residuais conhecidos

| Risco | Classificação | Motivo / mitigação |
| --- | --- | --- |
| Perda da `JURISDATA_DATA_KEY` | Ponto crítico | Torna ilegíveis os dados criptografados. Guardar em cofre, com cópia controlada |
| Vazamento conjunto de backup e chave | Ponto crítico | Guardar em locais e credenciais diferentes |
| Uso indevido por usuário autorizado | Ponto frágil | Justificativa, limite e auditoria reduzem e evidenciam, mas não impedem. Revisar a auditoria periodicamente |
| Administrador do servidor com acesso ao banco | Ponto frágil | Conteúdo criptografado; a trilha encadeada evidencia adulteração; restringir quem acessa o servidor |
| Formato da API CPF v3 não conferido | Questão indefinida | Ver [integracoes.md](integracoes.md) |
| Sem testes de intrusão independentes | Ponto frágil | Contratar antes da produção (fase 5 do cronograma) |

Referências: LGPD (<https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>) e
materiais da ANPD citados no projeto. Conferir a redação vigente antes de usar em documento formal.
