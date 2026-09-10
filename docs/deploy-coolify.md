# Runbook Coolify — preparação, não implantado

Atualização de implementação: compose.app.yml já está preparado e o parser Compose
5.1.4 validou os dois arquivos sem interpolação. As imagens da aplicação devem
vir exclusivamente dos contextos gerados por prepare_builds.py e do CI autorizado.
As instruções históricas de itens ainda pendentes abaixo devem ser lidas junto
de deployment-report.md e supabase-validation.md.

Versão observada: 4.3.18. Destino e baseline em environment.target.yml e docs.
Referência conferida: https://coolify.io/docs/knowledge-base/docker/compose

Projeto novo já criado: `jjxcrsedavkskvcbnuvmkaql`; staging vazio:
`xukzvsnkjemq085zitdzzytf`. Retomar pelo manifesto existente, nunca recriar por nome.
O ambiente padrão automaticamente criado pelo Coolify foi renomeado para staging.
Nenhum recurso de aplicação/dados está associado ao host ainda; project/environment
são metadados do painel, não comprovam implantação na VPS.

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

`infra/coolify/compose.data.yml` contém Redis/RabbitMQ/ClickHouse, sem portas públicas,
sem redes externas presumidas, com volumes exclusivos, limites, rotação de logs e
health checks. **É configuração proposta, ainda não validada pelo Docker Compose.**
É proibido implantar só porque o arquivo faz parse em YAML.

Antes de usar:

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

`compose.app.yml`, executor de migrations e deploy mutável ainda pendentes:
dependerão das correções DDL/TLS/contrato listadas em architecture-target.md e do
mapa Supabase. Não há loop automático de deploy enquanto Supabase está pendente.
Processos Rails de staging usarão RAILS_ENV=production, mas não serão iniciados
antes da validação do banco. Inicialmente restringir setup e criar admin com
procedimento seguro antes de permitir acesso geral.

## Operação

Definir checks externos e alertas fora da VPS: disco 75%/85%, RAM/CPU, reinícios,
idade de backups, Sidekiq pending/retry/failure/idade, Redis OOM/AOF, RabbitMQ
ready/unacked/alarms, ClickHouse e conexões/latência Supabase. Ainda não configurados.

Deploy Compose tem janela e shutdown gracioso; não prometer rolling/zero downtime.
Nenhum restart/upgrade/firewall/proxy global está autorizado como atalho.
