# JurisData — Central Jurídica de Consultas

Plataforma web privada para advogados e funcionários autorizados do escritório: consultas cadastrais
(CPF e CNPJ) por fontes oficiais contratadas, cadastro de clientes e processos, acompanhamento de
diligências patrimoniais requeridas ao juízo, relatórios em PDF e trilha de auditoria.

**Versão 0.1 (MVP).** Web responsiva (computador e celular), identidade visual *dark premium*,
empacotada em Docker para qualquer nuvem com região no Brasil ou servidor próprio.

> O JurisData **não** acessa SISBAJUD, RENAJUD, SNIPER, INFOJUD nem bases restritas da SENATRAN.
> Esses sistemas são operados pelo Judiciário ou dependem de autorização própria. Aqui só se registram
> os pedidos feitos ao juízo, as decisões e os resultados juntados aos autos.

## O que está pronto

| Área | Funcionalidade |
| --- | --- |
| Acesso | Login individual, senha com Argon2, **MFA obrigatório (TOTP)**, bloqueio após tentativas, sessão com expiração por inatividade e tempo máximo, troca de senha obrigatória no 1º acesso, termo de responsabilidade |
| Perfis | Administrador, Advogado, Assistente jurídico, Auditor (permissões abaixo) |
| Consultas | CPF (SERPRO v3: CPF + nascimento), CNPJ básica / QSA / empresa (SERPRO), CNPJ em dados públicos (BrasilAPI, opcional), conector **simulado** só para treinamento |
| Regras LGPD | Vínculo obrigatório a processo/demanda ativa, finalidade, base legal (art. 7º) e justificativa registradas **antes** da consulta; declaração de finalidade; limite de consultas em 24 h; aprovação de advogado para consultas de assistentes |
| Proteção de dados | CPF, nascimento, resultados e segredos de MFA **criptografados no banco**; CPF mascarado em telas, listas, PDF padrão e auditoria; busca na auditoria por HMAC, sem gravar o número |
| Falhas | Se a fonte falhar, a consulta fica “não concluída” e **nenhum dado antigo é exibido** |
| Relatórios | PDF com fonte, data/hora, finalidade, base legal, solicitante, aprovador, dados retornados e hash do conteúdo; versão integral (sem máscara) só para advogado, registrada à parte |
| Processos | Clientes, processos (numeração CNJ validada) ou demandas pré-processuais, encerramento |
| Diligências | SISBAJUD, RENAJUD, INFOJUD, SNIPER, CNIB, registro de imóveis, junta comercial: situação, decisão, prazos e andamentos |
| Auditoria | Trilha encadeada por hash (detecta alteração ou exclusão), filtros, exportação CSV |
| Retenção | Expurgo automático do conteúdo após o prazo configurado (padrão 365 dias), mantendo só metadados |

### Perfis

| Perfil | Pode | Não pode |
| --- | --- | --- |
| Administrador | Usuários, configurações, retenção, auditoria | Fazer consultas |
| Advogado | Consultas, processos, relatórios, aprovar/recusar consultas de assistentes, PDF integral | Aprovar a própria consulta |
| Assistente jurídico | Solicitar consultas (com aprovação), clientes, diligências, ver resultado das próprias consultas | Ver consultas de outros, PDF integral |
| Auditor | Histórico de consultas (metadados) e auditoria | Ver conteúdo retornado, alterar qualquer coisa |

## Executar localmente (teste)

```bash
cd jurisdata
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.cli gerar-chaves          # copie as duas linhas para o ambiente
```

```bash
export JURISDATA_SECRET_KEY=...  JURISDATA_DATA_KEY=...
export JURISDATA_COOKIE_SECURE=0 JURISDATA_MODO_SIMULADO=1
python -m app.cli criar-admin --nome "Seu Nome" --email voce@escritorio.adv.br
uvicorn app.main:app_factory --factory --port 8000
```

Abra http://localhost:8000, entre com a senha temporária exibida e cadastre o MFA no aplicativo
autenticador. Com `JURISDATA_MODO_SIMULADO=1` as consultas devolvem **dados fictícios** marcados como
tal. Para treinar falhas, use nascimento `01/01/1901` (dados não conferem) ou `02/02/1902` (fonte fora do ar).

Testes:

```bash
pytest
```

Contra PostgreSQL:

```bash
JURISDATA_TEST_DATABASE_URL="postgresql+psycopg://usuario:senha@host/banco_de_teste" pytest
```

## Implantação (produção)

```bash
cp .env.example .env    # preencha; em nuvem prefira o cofre de segredos
docker compose up -d --build
docker compose exec app python -m app.cli criar-admin --nome "..." --email "..."
```

Requisitos obrigatórios em produção (o sistema **recusa iniciar** sem eles): PostgreSQL, cookie `Secure`
(HTTPS) e conector simulado desligado. Publique somente atrás de proxy reverso com TLS e informe o IP do
proxy em `FORWARDED_ALLOW_IPS`.

Rotinas a agendar:

| Rotina | Comando | Frequência |
| --- | --- | --- |
| Expurgo por retenção | `docker compose exec app python -m app.cli expurgar` | diária |
| Integridade da auditoria | `docker compose exec app python -m app.cli verificar-auditoria` | diária |
| Backup criptografado do PostgreSQL | `pg_dump` + criptografia, fora do servidor | diária |
| Revisão de usuários e perfis | tela *Usuários* | mensal |

**Guarde a `JURISDATA_DATA_KEY` em cofre separado do backup.** Sem ela os dados criptografados não podem
ser lidos; com ela e o backup juntos, um vazamento expõe tudo.

## Estrutura

```
jurisdata/
├── app/
│   ├── main.py              aplicação, cabeçalhos de segurança (CSP, HSTS…)
│   ├── config.py            configuração por variáveis de ambiente
│   ├── models.py            banco de dados
│   ├── security.py          senhas, criptografia, HMAC, MFA, máscaras
│   ├── validators.py        CPF, CNPJ (inclusive alfanumérico), datas, número CNJ
│   ├── audit.py             trilha encadeada por hash
│   ├── lgpd.py              bases legais e finalidades
│   ├── connectors/          SERPRO, BrasilAPI, simulado (um conector por fonte)
│   ├── services/            fluxo de consulta, retenção, relatório PDF
│   ├── rotas_*.py           páginas
│   ├── templates/ static/   interface
│   └── cli.py               comandos administrativos
├── tests/                   41 testes (SQLite e PostgreSQL)
├── docs/                    integrações e governança LGPD
├── Dockerfile  docker-compose.yml  .env.example
```

Mais detalhes: [docs/integracoes.md](docs/integracoes.md) · [docs/lgpd-e-governanca.md](docs/lgpd-e-governanca.md)
