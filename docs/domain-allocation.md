# Alocação de domínios — REVIEW_REQUIRED

Owner: hablas-evo-infra / staging

## Destino de frontend informado posteriormente pelo responsável

O responsável definiu **crm.hablas.chat** como endereço do frontend para acesso
dos clientes. Os demais subdomínios podem ser escolhidos pelo executor, respeitando
inventário, isolamento e ausência de conflito.

No inventário inicial, crm.hablas.chat já possuía CNAME, ID
`b404a68855d7c9a4a2b569eb8afe11a8`. A revisão autenticada de 10/09/2026 confirmou
que o registro DNS-only apontava para `whitelabel.ludicrous.cloud`; a resolução
pública e uma requisição HTTPS retornaram a aplicação existente com HTTP 200.
Registros relacionados (`api-crm`, `lp.crm`, email e DKIM) confirmaram que não era
um registro abandonado.

O responsável informou a liberação do subdomínio e removeu os CNAMEs web. Às 15:13
UTC, `crm.hablas.chat`, `api-crm.hablas.chat` e `lp.crm.hablas.chat` não resolviam;
o painel também não listava CNAME/A/AAAA exato para o host principal. O CNAME de
e-mail e o DKIM sob `crm.hablas.chat` permanecem e não estão autorizados para
alteração. O host principal está disponível, mas ainda não foi vinculado ao Worker;
ver `docs/crm-cutover-plan.md`.

O hostname solicitado ainda não foi alocado nem vinculado ao Worker. Os candidatos
novos de homologação abaixo continuam sendo preparação, sem publicação.

Observação: 09/09/2026 22:28–22:30 America/Sao_Paulo.
Account: `85354ee4fc8d1c079a66f6321a5c78c5` (GoLevel).
Zone: `b0a4153d93f81cd7957e34cdfcd11e60` (hablas.chat).

| Host | DNS exato | Wildcard DNS | Worker/domain/Pages/Tunnel/LB | Decisão |
|---|---|---|---|---|
| crm.hablas.chat | Ausente após liberação | Ausente | Nenhum vínculo observado | Frontend final; deploy autorizado |
| api-crm.hablas.chat | Ausente após liberação | Ausente | Nenhum vínculo observado | API final; deploy autorizado |
| evo-stg.hablas.chat | Ausente | Ausente | Nenhum vínculo observado | Candidato; não reservado |
| evo-api-stg.hablas.chat | Ausente | Ausente | Nenhum vínculo observado | Candidato; não reservado |
| evo.hablas.chat | A existente | — | Não necessário investigar para rejeitar | Ocupado; preservar |

As regras custom WAF e redirect lidas têm escopo em outros hostnames exatos.
As rotas `hablas.chat/*` e `www.hablas.chat/*` existentes são do sistema atual.
Não criar wildcard nem atualizar registros preexistentes.

Faltam: inventário completo de domínios Coolify/proxy, cookies no domínio pai,
revisão de regras gerenciadas/configurações aplicáveis e solução de TLS strict
isolada ao hostname. O SSL global é Full; não alterar globalmente.

`frontend_host` e `api_host` continuam nulos até a alocação autenticada. Nenhum DNS,
domínio, Worker ou Access foi criado por esta implantação. O responsável escolheu
os hosts finais, fresh start e autorizou staging + GO final em sequência. Uma nova
leitura API às 17:37 UTC confirmou os quatro hosts ainda livres. Reexecutar preflight
autenticado imediatamente antes da escrita; qualquer falta de
permissão/paginação/configuração gera BLOCKED.
