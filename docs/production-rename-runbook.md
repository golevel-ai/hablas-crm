# Runbook: rename físico staging → production e cutover para crm.hablas.chat

Estado: **FASES 1-3 CONCLUIDAS / FASES 4-8 PENDENTES**
Owner: hablas-evo-infra
Escopo autorizado: `cutover.rename_scope = FULL_PHYSICAL_RENAME_STAGING_TO_PRODUCTION`

Este runbook cobre o que o cutover de hostname sozinho não cobre: renomear os
recursos físicos cujo identificador está gravado em dados, não em configuração.

## Por que isto não é uma troca de nomes

Quatro recursos não aceitam rename no lugar. Cada um exige movimentação de dados:

| Recurso | Identificador gravado em dados | Consequência de ignorar |
|---|---|---|
| Bucket R2 | Nome do bucket, imutável na API R2 | Toda a mídia do CRM e do Auth fica inacessível |
| RabbitMQ | `RABBITMQ_NODENAME` na base Mnesia | Filas, exchanges, bindings e o vhost ficam ilegíveis |
| Role Postgres | Hash da senha vinculado ao nome | `ALTER ROLE ... RENAME` invalida a senha dos 9 serviços |
| Volume Docker | Nome do volume | Docker cria volume vazio; não move dados |

O Worker e os pacotes GHCR também não são renomeáveis, mas são artefatos
reconstruíveis: basta republicar sob o nome novo.

## Pré-requisitos

1. Janela de manutenção aprovada, com responsável de negócio e canal de escalonamento.
2. O responsável autorizou explicitamente o descarte dos dados existentes para este
   fresh start (`OWNER_AUTHORIZED_DISCARD_EXISTING_DATA`). A dispensa de restore vale
   apenas para esta execução; ver `docs/backup-restore.md`.
3. Imagens de produção construídas e verificadas. `scripts/ops/ops.py` bloqueia o
   deploy remoto enquanto `infra/versions.lock.yml` apontar para pacotes pré-rename.
4. Inventário Cloudflare reexecutado imediatamente antes de qualquer escrita.

## Ordem de execução

A ordem importa. Cada fase é reversível até a Fase 7.

### Fase 1 — Construir os artefatos de produção

Nada remoto é alterado.

1. Criar a branch `infra/production-deployment` e publicar. O workflow
   `.github/workflows/build-production.yml` só dispara nela.
2. O CI reconstrói as sete imagens sob `ghcr.io/golevel-ai/hablas-evo-production-*`
   e o bundle do frontend com as origens finais (`https://api-crm.hablas.chat`).
3. Importar os recibos com `scripts/ops/import_release.py`. Ele agora recusa
   qualquer recibo que não aponte para o pacote `hablas-evo-production-*`.

Saída: `infra/versions.lock.yml` com sete digests verificados e
`verification = ANONYMOUS_PULL_AND_DIGEST_VERIFIED`.

### Fase 2 — Criar o bucket R2 de produção e copiar a mídia

Buckets R2 não são renomeáveis. As chaves dos objetos **devem** ser copiadas
literalmente: o ActiveStorage grava a chave do blob no Postgres, não o nome do
bucket. Alterar a chave quebra todos os anexos existentes.

1. Criar `hablas-evo-production-media` e `hablas-evo-production-backups` na mesma
   região do bucket atual.
2. Copiar objeto a objeto preservando a chave, o content-type e os metadados.
3. Conferir contagem de objetos e checksum de uma amostra em ambos os buckets.
4. Confirmar que o bucket novo continua privado: um GET anônimo deve ser negado.

Não apagar os buckets de staging nesta fase. Eles são o fallback da Fase 7.

### Fase 3 — Criar as roles de produção no Supabase

`ALTER ROLE ... RENAME` invalida a senha quando ela é SCRAM/md5, e o pooler do
Supabase usa o formato `role.projectref`. Criar roles novas é mais previsível do
que renomear e rotacionar no escuro.

1. Criar `hablas_evo_prod_main` e `hablas_evo_prod_main_migrator` com senhas novas.
2. Replicar exatamente os grants das roles de staging, incluindo o schema do EvoFlow.
3. Renomear o schema `hablas_evoflow_staging` para `hablas_evoflow_production` e
   reaplicar os grants; o EvoFlow lê o schema por `POSTGRES_DB_SCHEMA`.
4. Validar login das duas roles novas por conexão TLS `verify-full` antes de seguir.
5. Só revogar as roles antigas na Fase 8, após a janela de observação.

Concluída em 12/09/2026: as quatro roles de produção foram criadas com os limites
previstos, o schema foi renomeado e os logins/grants foram confirmados por TLS
`verify-full`. O runtime EvoFlow pode apenas ler sua tabela `migrations`, requisito
do guard `showMigrations()`; alterações permanecem exclusivas da role migrator.

### Fase 4 — Parar escritas e drenar as filas

A partir daqui há indisponibilidade. Esta é a única fase que não pode ser parcial.

1. Parar os serviços produtores: `crm`, `crm-sidekiq`, `auth-sidekiq`, `evoflow`,
   `bot`, `processor`.
2. Aguardar Sidekiq chegar a zero em `enqueued`, `scheduled` e `retry`. Um volume
   Redis vazio na fase seguinte perde todo job pendente, de forma irrecuperável.
3. Aguardar todas as filas RabbitMQ chegarem a zero mensagens prontas e não-ack.
4. Exportar as definitions do RabbitMQ (topologia; **não** contém mensagens).
5. Capturar evidência: contagens, offsets e um dump lógico do Postgres.

### Fase 5 — Mover os volumes

Docker cria volumes vazios para os nomes novos. Copiar explicitamente.

- **Redis** (`hablas-evo-staging-redis` → `hablas-evo-production-redis`): copiar o
  conteúdo com o container parado, para que o AOF esteja consistente.
- **ClickHouse** (`...-staging-clickhouse` → `...-production-clickhouse`): copiar
  com o servidor parado; em seguida renomear a base e recriar o usuário e os grants
  (`CLICKHOUSE_DB`/`CLICKHOUSE_USER` passaram a `hablas_evo_production`). Um volume
  vazio perde todo o histórico de eventos de contato do EvoFlow.
- **RabbitMQ**: **não copiar**. `RABBITMQ_NODENAME` mudou para
  `rabbit@hablas-evo-production-rabbitmq` e o Mnesia antigo é ilegível sob nodename
  novo. Subir o nó novo vazio e importar as definitions da Fase 4. Por isso a Fase 4
  exige filas em zero: definitions não carregam mensagens.

Manter `RABBITMQ_ERLANG_COOKIE` estável entre as duas stacks; ele é segredo de
recuperação, não identidade de nó.

### Fase 6 — Subir a stack de produção

1. Aplicar `infra/coolify/compose.data.yml` (stack `hablas-evo-data-production`).
2. Importar as definitions do RabbitMQ e conferir a topologia.
3. Aplicar `infra/coolify/compose.app.yml` (stack `hablas-evo-app-production`) com
   `FRONTEND_ORIGIN=https://crm.hablas.chat` e
   `API_ORIGIN=https://api-crm.hablas.chat`.
4. Atualizar todos os `*_UPSTREAM` e `*_INTERNAL_ORIGIN`: os nomes de serviço
   mudaram e o Coolify anexa o UUID do recurso ao hostname interno. O gateway
   resolve esses nomes; se um ficar para trás, a rota correspondente cai.
5. Confirmar os nove processos healthy **antes** de publicar qualquer hostname.

### Fase 7 — Túnel e publicação

Ponto de não-retorno para o tráfego de cliente.

1. Criar o tunnel `hablas-evo-production` e gravar o UUID em
   `cloudflare.tunnel.id` (`infra/environment.target.yml`). O preflight remoto
   bloqueia enquanto ele for `null`.
2. Gravar `TUNNEL_TOKEN` como segredo do recurso Coolify e aplicar
   `infra/coolify/compose.tunnel.yml`. São dois conectores:
   um único `cloudflared` seria ponto único de falha para toda a API.
3. Confirmar os dois conectores registrados e saudáveis no painel.
4. Criar a rota DNS de `api-crm.hablas.chat` apontando para o tunnel, **não** um
   registro A para `51.81.80.55`.
5. Validar a API pelo hostname final: TLS, CORS, login, refresh, `wss://.../cable`
   e o streaming SSE do processor. O `/cable` e o SSE são o que mais provavelmente
   revela erro de configuração do túnel; testar os dois explicitamente.
6. Só então anexar `crm.hablas.chat` como Custom Domain do Worker
   `hablas-evo-frontend-production`. Confirmar antes que não existe
   CNAME/A/AAAA/Worker/Pages/Tunnel/LB conflitante no host.
7. Executar smoke anônimo e autenticado antes de anunciar.

Ainda **não** fechar as portas 80/443 na origem. Mantê-las abertas durante a
observação preserva o caminho de rollback direto.

### Fase 8 — Observação e limpeza

Nenhum item aqui é executado no dia do cutover.

1. Observar pelo período aprovado, com os limiares de rollback de
   `docs/crm-cutover-plan.md`.
2. Fechar as portas 80/443 na origem e marcar
   `cloudflare.tunnel.origin_ports_closed = true`. O guard recusa esta marcação
   enquanto o tunnel não existir.
3. Remover os hostnames de homologação listados em `cloudflare.retired_hosts`.
4. Revogar as roles Postgres antigas e os buckets R2 de staging.
5. Renomear o projeto Supabase para `hablas-evo-production`.

## Rollback

O rollback depende da fase em que a falha aparecer.

- **Antes da Fase 4**: nada de cliente mudou. Abandonar a janela.
- **Fases 4 a 6**: religar a stack de staging com os volumes originais, que
  permanecem intactos porque a Fase 5 **copia** em vez de mover. As roles novas do
  Supabase são aditivas; as antigas continuam válidas até a Fase 8.
- **Fase 7 em diante**: seguir o procedimento de rollback de tráfego em
  `docs/crm-cutover-plan.md`. Congelar escritas e reconciliar antes de reverter DNS;
  sem isso o resultado é split-brain, não rollback.

O rollback de tráfego para o fornecedor anterior (`whitelabel.ludicrous.cloud`)
continua **não comprovado**: a liberação do domínio não demonstra que o fornecedor
voltará a aceitá-lo. Confirmar com o fornecedor antes da janela ou aceitar
explicitamente que esse caminho não existe.

## Referências

- `infra/environment.target.yml`
- `infra/coolify/compose.app.yml`, `compose.data.yml`, `compose.tunnel.yml`
- `infra/cloudflare/tunnel-config.yml`, `wrangler.jsonc`
- `scripts/ops/ops.py` (`validate_target`, `validate_tunnel`, `unverified_production_images`)
- `docs/crm-cutover-plan.md`, `docs/backup-restore.md`, `docs/rollback.md`
- Cloudflare Tunnel, parâmetros de origem:
  https://developers.cloudflare.com/tunnel/reference/origin-parameters/
- Cloudflare Workers Custom Domains:
  https://developers.cloudflare.com/workers/configuration/routing/custom-domains/
