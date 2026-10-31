# Integrações — situação e pendências

Referência: 31/10/2026. Endpoints e formatos de fornecedores mudam; confira sempre a documentação do
contrato antes de configurar. Nenhum endereço de API de terceiro está fixado no código: tudo é
configurado por variável de ambiente.

## Resumo

| Fonte | Situação no JurisData | O que falta |
| --- | --- | --- |
| SERPRO — Consulta CNPJ (básica, QSA, empresa) | Conector pronto e testado com servidor simulado | Contratar (e-CNPJ); copiar URL do token e URL base da versão contratada |
| SERPRO — Consulta CPF v3 | Conector pronto; exige CPF + nascimento | Contratar; **conferir na documentação como a data de nascimento é enviada** e montar o modelo de URL |
| BrasilAPI — CNPJ público | Conector pronto, desligado por padrão | Decidir se será usado (dado público, pode estar defasado) |
| SENATRAN — veículos | **Não implementado** | Solicitar credenciamento; só integrar depois do TAAD |
| SISBAJUD / RENAJUD / SNIPER / INFOJUD | Fora do escopo por definição | Acesso restrito ao Judiciário; usar o módulo de diligências |

## SERPRO — Consulta CPF v3

### Divergência encontrada no projeto original

O projeto indicava o endpoint `https://gateway.apiserpro.serpro.gov.br/consulta-cpf-df/v3`.
O aviso de lançamento da v3 publicado pelo SERPRO (Central de Ajuda, versão em inglês:
<https://centraldeajuda.serpro.gov.br/duvidas/en/warnings/warningcpfv3query/>) indica outro endereço:

```
https://apicpf.estaleiro.serpro.gov.br/api/v3/cpf/
```

Pontos do mesmo aviso e da notícia do SERPRO sobre a nova versão
(<https://www.serpro.gov.br/menu/noticias/noticias-2026/nova-versao-da-consulta-cpf>):

- a v3 passou a valer em 29/05/2026 e exige **CPF e data de nascimento**;
- a chave de acesso do contrato continua a mesma;
- **não há ambiente de testes da v3**: toda requisição conta como uso de produção (cobrada);
- o retorno traz nome, situação cadastral, nome social (quando houver) e data de inscrição; o ano de
  óbito deixou de ser retornado; a data de nascimento serve só para conferência e não é devolvida.

[NECESSÁRIO CONFERIR NA DOCUMENTAÇÃO] Este levantamento foi feito por busca na web; as páginas oficiais
não puderam ser abertas diretamente a partir do ambiente de desenvolvimento. Antes de configurar,
confira no API Center (<https://apicenter.estaleiro.serpro.gov.br>):

1. o endpoint exato;
2. como a data de nascimento é enviada (caminho, parâmetro de consulta ou corpo) e em que formato;
3. a URL do token OAuth2 do contrato;
4. o código HTTP usado quando CPF e nascimento não conferem.

### Como configurar

`JURISDATA_SERPRO_CPF_URL_TEMPLATE` é um modelo de URL com os marcadores:

| Marcador | Valor |
| --- | --- |
| `{cpf}` | 11 dígitos, sem pontuação |
| `{nascimento_ddmmaaaa}` | ex.: `10051980` |
| `{nascimento_iso}` | ex.: `1980-05-10` |

O sistema só oferece a consulta de CPF quando o modelo contém `{cpf}` e um marcador de nascimento.
O conector usa `GET` com token Bearer. Se a documentação exigir `POST` com corpo JSON, o conector
precisa de um ajuste pequeno em `app/connectors/serpro.py` (método `consultar`).

Como não há ambiente de testes da v3, faça a homologação com **uma única consulta real**, de CPF próprio
e com finalidade registrada, depois de conferir o formato.

## SERPRO — Consulta CNPJ

`JURISDATA_SERPRO_CNPJ_URL` recebe a URL base da versão contratada; o conector acrescenta
`/basica/{cnpj}`, `/qsa/{cnpj}` ou `/empresa/{cnpj}` conforme a modalidade.
[CONFERIR NA DOCUMENTAÇÃO DO CONTRATO] se esse é o padrão da versão contratada e se o ambiente de
demonstração (até 30 dias ou 3.000 consultas, segundo a página de contratação) usa outra URL.

CNPJ alfanumérico: o sistema valida o novo formato (IN RFB nº 2.229/2024). Se a versão contratada da
API ainda não aceitar letras, a fonte devolverá erro e a consulta ficará “não concluída”.

## Tratamento de respostas (todas as fontes)

| Resposta da fonte | Situação da consulta | Mensagem |
| --- | --- | --- |
| 200 | Concluída | dados exibidos e guardados criptografados |
| 404 | Não concluída | documento não localizado ou dados não conferem |
| 400 / 422 | Não concluída | requisição recusada; conferir dados |
| 401 | Renova o token uma vez; se persistir, não concluída | credencial recusada |
| 403 | Não concluída | acesso negado pelo contrato |
| 429 | Não concluída | limite da fonte atingido |
| 5xx, tempo esgotado, rede | Não concluída | fonte indisponível |

Em nenhum caso o sistema mostra resultado anterior no lugar de uma consulta que falhou.

O retorno é guardado **como veio da fonte**, sem renomear campos, e exibido como lista campo → valor.
Assim uma mudança de esquema do fornecedor não gera dado inventado ou campo trocado.

## SENATRAN — veículos (fase 4)

Não implementado de propósito. Segundo a documentação do SERPRO/SENATRAN e a Portaria SENATRAN
nº 139/2025, entidades privadas precisam comprovar relação da atividade com trânsito, veículos,
financiamento, seguros e afins; escritório de advocacia não tem aprovação presumida. A integração só
deve ser desenvolvida depois do Termo de Autorização de Acesso a Dados (TAAD). Enquanto isso, a via
para execução é o pedido de pesquisa RENAJUD ao juízo, registrado no módulo de diligências.

## Como acrescentar uma fonte

1. Criar `app/connectors/<fonte>.py` com `id`, `rotulo`, `tipos` e `consultar()` devolvendo
   `ResultadoConsulta` ou levantando uma subclasse de `ErroConector`.
2. Registrar em `app/connectors/__init__.py`.
3. Testar com `httpx.MockTransport` (ver `tests/test_conectores.py`).
