# Runbook Coolify — dados implantados, aplicação bloqueada

Atualização de implementação: compose.app.yml já está preparado e o parser Compose
5.1.4 validou os dois arquivos sem interpolação. As imagens da aplicação devem
vir exclusivamente dos contextos gerados por prepare_builds.py e do CI autorizado.
As instruções históricas de itens ainda pendentes abaixo devem ser lidas junto
de deployment-report.md e supabase-validation.md.

Versão observada: 4.3.18. Destino e baseline em environment.target.yml e docs.
Referência conferida: https://coolify.io/docs/knowledge-base/docker/compose

Projeto `jjxcrsedavkskvcbnuvmkaql` e ambiente `xukzvsnkjemq085zitdzzytf` já existem.
Retomar pelos UUIDs e manifesto existentes, nunca recriar por nome.

> Atualização de 12/09/2026 — rename físico autorizado. Os nomes de stack e de
> serviço em `compose.app.yml` e `compose.data.yml` passaram de `*-staging-*` para
> `*-production-*`. Isso **não** é cosmético no Coolify: o hostname interno de cada
> serviço deriva do nome do serviço com o UUID do recurso anexado, então todos os
> `*_UPSTREAM` e `*_INTERNAL_ORIGIN` mudam junto e o gateway precisa ser atualizado
> na mesma operação. Os volumes renomeados nascem **vazios**; ver
> `docs/production-rename-runbook.md` antes de aplicar.
>
> O domínio da API deixa de ser configurado no proxy do Coolify: `api-crm.hablas.chat`
> passa a ser publicado por Cloudflare Tunnel (`infra/coolify/compose.tunnel.yml`),
> que alcança o gateway pela rede Docker. Não associar domínio público ao gateway no
> painel do Coolify para esse host.

## Verificações locais disponíveis

Executar da raiz (os wrappers podem ser chamados com bash):

```bash
bash scripts/ops/validate.sh --target infra/environment.target.yml
bash scripts/ops/preflight.sh --target infra/environment.target.yml --stage local
bash scripts/ops/preflight.sh --target infra/environment.target.yml --stage remote
```

O último deve retornar **2/BLOCKED** enquanto as pendências persistirem.
PASS local valida identidade/política/gitlinks, não runtime ou prontidão.
Arquivos `.yml` de target/lock/manifest usam notação JSON, subconjunto de YAML 1.2,
para parsing estrito com Python sem dependências. Não converter para YAML livre
sem atualizar o parser. `compose.data.yml` é YAML Compose normal.

## Preparação dos dados

`infra/coolify/compose.data.yml` define o recurso de dados já implantado: Redis,
RabbitMQ e ClickHouse sem portas públicas, com volumes exclusivos, limites, rotação
de logs e health checks. O Compose passou no parser 5.1.4 e os três serviços estão
healthy no servidor registrado. Isto não autoriza alteração nem reimplantação.

Antes de alterar ou reimplantar:

1. Aprovar imagens/digests reais para linux/amd64 e gravar em versions.lock/manifesto.
   Os campos de env.data.example ficam vazios até isso; `:?` bloqueia vazios,
   mas não detecta sozinho imagens mutáveis nem credenciais de exemplo.
2. Verificar novamente nomes de projeto/ambiente/recurso/volume e proprietário.
   Gerar marcador exclusivo uma única vez. Em retomadas comparar UUID + marcador;
   homônimos desconhecidos bloqueiam a operação.
3. Definir segredos dedicados em Coolify/cofre. Não usar a geração automática
   de senhas por serviço para chaves que precisam ser iguais entre processos.
4. Confirmar orçamento de memória da aplicação + dados + workloads existentes.
5. Validar Compose normal com `docker compose ... config --quiet` no ambiente
   autorizado, sem imprimir env expandido. Verificar suporte/materialização dos
   arquivos `configs` relativos a infra/coolify e os limites efetivos.
6. Criar os dois recursos só após preflight de não interferência. Não instalar
   Coolify nem executar um segundo `compose up` via SSH.
7. Conectar aos networks suportados pelo Coolify, registrar nomes sufixados por
   UUID, testar DNS/TCP de cada consumidor. Configurar domínio só no gateway,
   usando a porta interna :3030 no campo de domínio Coolify.

## Aplicação / migrations

`compose.app.yml`, overlays DDL/TLS, banco Supabase dedicado e bootstrap de schemas
estão preparados/validados conforme `deployment-report.md`. Ainda faltam imagens da
receita atual, testes de container, criação autorizada da aplicação e deploy. Processos
Rails de staging usarão `RAILS_ENV=production`. Criar o primeiro admin pela rede
interna antes de associar qualquer domínio, conforme `crm-cutover-plan.md`.

## Operação

Definir checks externos e alertas fora da VPS: disco 75%/85%, RAM/CPU, reinícios,
idade de backups, Sidekiq pending/retry/failure/idade, Redis OOM/AOF, RabbitMQ
ready/unacked/alarms, ClickHouse e conexões/latência Supabase. Ainda não configurados.

Deploy Compose tem janela e shutdown gracioso; não prometer rolling/zero downtime.
Nenhum restart/upgrade/firewall/proxy global está autorizado como atalho.
