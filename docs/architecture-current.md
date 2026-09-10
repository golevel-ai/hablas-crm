# Arquitetura encontrada no fork

Fonte: `golevel-ai/hablas-crm`, commit `fa6924df23b863de30b065d25e301bb414593bd5`.
Os sete componentes principais estão nos gitlinks v1.1.0; ver lock completo.
Arquivos lidos: Compose local/Swarm, Makefile, Dockerfiles/entrypoints,
configurações de banco/storage, clientes HTTP/WS do frontend e gateway.

| Serviço | Linguagem/build | Processo / porta interna | Dependências / persistência | Health / migrations |
|---|---|---|---|---|
| Frontend | React 19, TS/Vite 6; Docker Node 20, npm ci, package-lock | `npm run build` → dist; Nginx upstream :80 | APIs/WS; assets estáticos | Nginx `/health`; sem migrations |
| Gateway | nginx/Dockerfile | Nginx :3030 | Auth, CRM, Core, Processor, Bot; sem dados locais | `/health` encaminha ao Processor, não prova todos os upstreams |
| Auth | Ruby/Rails, Dockerfile | Puma/Rails :3001 | PostgreSQL compartilhado, Redis DB1, S3 ActiveStorage | `/health`; entrypoint migra por padrão; gate RUN_MIGRATIONS=false |
| Auth Sidekiq | Mesma imagem Auth | `bundle exec sidekiq -C config/sidekiq.yml`, sem HTTP | PostgreSQL/Redis DB1; anexos em S3 | Não herdar health HTTP; precisa heartbeat/fila; desativar migrations |
| CRM | Ruby/Rails, docker/Dockerfile | Rails :3000 | Mesmo PostgreSQL; Redis DB0 local/DB1 Swarm; Auth/Core/Bot/EvoFlow; S3 | `/health/live`; entrypoint espera indefinidamente, usa set -x e db:prepare por padrão |
| CRM Sidekiq | Mesma imagem CRM | Sidekiq, sem HTTP | Mesmos serviços/segredos/storage CRM | Mesmo gate; health de processo e atraso de filas a validar |
| Core | Go, go.community.mod, Dockerfile | `/app/main` :5555 | PostgreSQL compartilhado; Auth/Processor/CRM | `/health`; entrypoint executa migrate antes de main; tabela própria de migrations |
| Processor | Python 3.11/FastAPI; requirements.txt | Uvicorn src.main:app :8000 | PostgreSQL, Redis, Auth/Core/CRM; logs; adaptador de artifacts | `/health` e readiness a testar; CMD roda Alembic e seeders automaticamente |
| Bot Runtime | Go, Dockerfile | Binário; LISTEN_ADDR :8080 | Redis, Processor, CRM postback; allowlist de mídia | `/health`; sem PostgreSQL neste deploy |
| EvoFlow | Node 20/NestJS/TypeORM | `node dist/main.js`, PORT=3334 | Banco próprio, Redis DB4, RabbitMQ e ClickHouse | `/health` liveness, `/ready` readiness; migrations TypeORM fora do boot no alvo |
| Redis | Imagem upstream mutável | redis-server :6379 | Filas Sidekiq, cache/sessões/bots; volume /data | redis-cli ping autenticado; AOF e noeviction no alvo |
| RabbitMQ | rabbitmq:3-alpine upstream | Broker :5672 | Exigido no boot EvoFlow, mesmo api/direct; /var/lib/rabbitmq | rabbitmq-diagnostics; identidade estável e backup consistente |
| ClickHouse | Imagem upstream latest | HTTP :8123, nativo :9000 | EvoFlow contact_events, DB evo_campaign; /var/lib/clickhouse | Consulta autenticada; cria DB/tabelas de eventos; persistência obrigatória |

Variáveis reais e sensibilidades: `environment-matrix.md`. Banco: `database-map.md`.
Serviços de desenvolvimento PostgreSQL/Mailhog não fazem parte do alvo.
`evolution-api`, `evolution-go` e `evo-nexus` estão no repositório, mas não são
serviços do Compose de implantação auditado. Não instalar outro provedor WhatsApp
automaticamente; canais externos e credenciais de teste permanecem pendentes.

## Divergências operacionais

- Swarm: latest, placement/labels externos, rede evonet presumida, migrations
  com falhas ignoradas e loops de espera sem limite. Não usar como deploy Coolify.
- Redis DBs divergem entre os dois Composes. Escolha de staging deve preservar
  a consistência entre cada web/Sidekiq; não apresentar DBs lógicos como isolamento.
- Auth e CRM compartilham tabelas/schema/history. O Makefile carrega schema mestre
  CRM e marca migrations Auth, sem comprovar equivalência para Supabase.
- TLS: Rails não lê POSTGRES_SSLMODE; Core lê DB_SSLMODE; Processor usa DSN;
  EvoFlow `require` configura rejectUnauthorized=false. Banco ainda bloqueado.
- Campanhas continuam usando o cliente direto EvoFlow no frontend; segments/journeys
  usam proxy CRM. O gateway não possui upstream EvoFlow nem rota campaigns.
- Frontend Docker substitui placeholders no startup; isso não existe no Workers.
- Cookies hardcoded: `_evo_auth_service_session`, `_evolution_session`, refresh
  `_evo_rt`/legado. Conferir todos os pontos de leitura/escrita e cookies no domínio
  pai antes de configurar nomes exclusivos; host-only por si só não evita colisão
  com cookies herdados de outro sistema.
- Auth storage consulta DB antes de ENV, CRM usa ENV primeiro. Conferir configuração
  efetiva dos dois, sem apenas repetir variáveis S3.
- Processor possui ARTIFACT_* além de STORAGE_* Rails: mapear MinIO/S3, URLs temporárias
  e auto-criação de buckets antes de declarar toda mídia persistida no R2.
- Processor executa `Base.metadata.create_all` em src/main.py:225 ao importar
  a aplicação. Trocar só o CMD não desativa esse DDL. Seu CORS também está hardcoded
  com origem `*`, sem consumir CORS_ORIGINS nesse middleware.

Esta auditoria não comprova isolamento multi-tenant nem altera a camada SaaS.
