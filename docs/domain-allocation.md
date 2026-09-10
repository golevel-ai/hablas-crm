# Alocação de domínios — REVIEW_REQUIRED

Owner: hablas-evo-infra / staging

## Destino de frontend informado posteriormente pelo responsável

O responsável definiu **crm.hablas.chat** como endereço do frontend para acesso
dos clientes. Os demais subdomínios podem ser escolhidos pelo executor, respeitando
inventário, isolamento e ausência de conflito.

No inventário inicial, crm.hablas.chat já possuía CNAME, ID
`b404a68855d7c9a4a2b569eb8afe11a8`. Antes da publicação, confirmar destino e uso
atual e registrar a transição especificamente autorizada, quando necessária.
O hostname solicitado ainda não foi alocado nem vinculado ao Worker. Os candidatos
novos de homologação abaixo continuam sendo preparação, sem publicação.

Observação: 09/09/2026 22:28–22:30 America/Sao_Paulo.
Account: `85354ee4fc8d1c079a66f6321a5c78c5` (GoLevel).
Zone: `b0a4153d93f81cd7957e34cdfcd11e60` (hablas.chat).

| Host | DNS exato | Wildcard DNS | Worker/domain/Pages/Tunnel/LB | Decisão |
|---|---|---|---|---|
| evo-stg.hablas.chat | Ausente | Ausente | Nenhum vínculo observado | Candidato; não reservado |
| evo-api-stg.hablas.chat | Ausente | Ausente | Nenhum vínculo observado | Candidato; não reservado |
| evo.hablas.chat | A existente | — | Não necessário investigar para rejeitar | Ocupado; preservar |

As regras custom WAF e redirect lidas têm escopo em outros hostnames exatos.
As rotas `hablas.chat/*` e `www.hablas.chat/*` existentes são do sistema atual.
Não criar wildcard nem atualizar registros preexistentes.

Faltam: inventário completo de domínios Coolify/proxy, cookies no domínio pai,
revisão de regras gerenciadas/configurações aplicáveis e solução de TLS strict
isolada ao hostname. O SSL global é Full; não alterar globalmente.

`frontend_host` e `api_host` continuam nulos. Nenhum DNS, domínio, Worker ou
Access foi criado. Reexecutar preflight autenticado imediatamente antes da escrita;
qualquer falta de permissão/paginação/configuração gera BLOCKED.
