# Matriz inicial de ambiente

Valores secretos não são definidos aqui. `obrigatória` significa exigida no alvo,
mesmo quando o upstream possui fallback inseguro. Todas as variáveis desta tabela
são runtime, salvo as linhas VITE. Fonte: arquivos nos commits de versions.lock.

| Variável / família real | Consumidor | Obrigatória / origem | Sensível | Default do alvo |
|---|---|---|---|---|
| POSTGRES_HOST/PORT/USERNAME/PASSWORD/DATABASE | Auth, CRM, Sidekiq | Sim; conexão principal Supabase | PASSWORD/DSN sim | Nenhuma conexão default |
| PGSSLMODE, PGSSLROOTCERT | libpq de Rails | TLS + CA a validar | Não | verify-full; CA validada |
| DB_PGBOUNCER | CRM | Modo de conexão | Não | false (direct/session) |
| RAILS_ENV | Auth/CRM/Sidekiq | Sim | Não | production no container, recurso staging |
| RUN_MIGRATIONS | Auth/CRM/Sidekiq | Sim | Não | false; não desativa DDL do Processor |
| RAILS_MAX_THREADS, SIDEKIQ_CONCURRENCY | Rails/Sidekiq | Orçamento | Não | Proposta 3/3, validar runtime |
| DB_HOST/PORT/USER/PASSWORD/NAME/SSLMODE | Core | Sim; principal Supabase | PASSWORD sim | verify-full, sem fallback |
| DB_MAX_IDLE_CONNS/DB_MAX_OPEN_CONNS | Core | Orçamento | Não | Proposta 3/10 |
| DB_CONN_MAX_LIFETIME/DB_CONN_MAX_IDLE_TIME | Core | Orçamento | Não | Proposta 1h/30m |
| POSTGRES_CONNECTION_STRING | Processor | Sim; principal Supabase | Sim | Nenhuma; percent-encoding e TLS |
| POSTGRES_DB_HOST/PORT/USERNAME/PASSWORD/DATABASE | EvoFlow | Sim; banco dedicado validado | PASSWORD sim | Nenhuma |
| POSTGRES_SSLMODE | EvoFlow | TLS, configuração a corrigir | Não | Sem valor seguro suportado atualmente |
| SECRET_KEY_BASE | Rails e consumidores existentes | Sim; cofre, gerar uma vez | Sim | Sem default |
| JWT_SECRET_KEY | Auth/CRM/Core/Processor | Sim; mesma assinatura compatível | Sim | Sem default; impedir fallback aleatório Processor |
| DOORKEEPER_JWT_SECRET_KEY/ALGORITHM/ISS | Auth/Sidekiq Auth | OAuth compatível com código | Chave sim | Sem chave default |
| ENCRYPTION_KEY / EVO_AI_ENCRYPTION_KEY | Core+Processor / CRM+Sidekiq | Mesma chave Fernet base64url de 32 bytes | Sim | Gerar uma vez; cópia de recuperação |
| EVOAI_CRM_API_TOKEN | Serviços internos | Sim; compartilhado conforme contrato | Sim | Sem default |
| BOT_RUNTIME_SECRET | CRM/Sidekiq/Bot | Sim; compartilhado | Sim | Sem default |
| AUTH_APIKEY_INTEGRATION_LOCAL | CRM/Sidekiq/EvoFlow | Sim; compartilhado | Sim | Sem default |
| REDIS_URL | Rails/Sidekiq/Bot | Sim; DNS real com UUID e senha codificada | Sim | DBs consistentes web/worker; decisão pendente |
| REDIS_HOST/PORT/PASSWORD/DB/SSL | Processor/EvoFlow | Sim | PASSWORD sim | DB1 Processor, DB4 EvoFlow propostos; validar |
| REDIS_KEY_PREFIX | Processor | Código | Não | a2a_ no Swarm, conferir contratos |
| RABBITMQ_URL | EvoFlow | Broker novo, vhost exclusivo | Sim | URI codificada, sem guest |
| RABBITMQ_DEFAULT_USER/PASS/VHOST/ERLANG_COOKIE/NODENAME | Broker | Cofre e identidade estável | PASS/COOKIE sim | Prefixos staging; sem default secreto |
| CLICKHOUSE_HOST/PORT/DATABASE/USERNAME/PASSWORD/TABLE | EvoFlow | Storage novo | PASSWORD sim | contact_events; DB exclusivo |
| CLICKHOUSE_USER/PASSWORD/DB | ClickHouse | Usuário e DB exclusivo | PASSWORD sim | hablas_evo_staging; senha obrigatória |
| RUN_MODE/QUEUE_MODE/STORAGE_MODE/WRITE_MODE | EvoFlow | Contrato do commit | Não | api/direct/clickhouse/ch-sync; sem prometer fila no fluxo direto |
| ACTIVE_STORAGE_SERVICE | Auth/CRM/Sidekiq | Sim | Não | s3_compatible |
| STORAGE_BUCKET_NAME/ACCESS_KEY_ID/SECRET_ACCESS_KEY/REGION/ENDPOINT | Rails ActiveStorage | Sim; R2 privado dedicado | Credenciais sim | region=auto, sem bucket default |
| ACTIVE_STORAGE_URL | Rails | URL de mídia, validar adapter | Não | Host API validado, sem URL pública de bucket |
| ARTIFACT_SERVICE_TYPE/ENDPOINT/ACCESS_KEY/SECRET_KEY/SECURE/REGION | Processor | Adaptador de artifacts; auditoria pendente | Credenciais sim | Sem MinIO default em produção |
| ARTIFACT_SPEECH_BUCKET/FILES_BUCKET/AUTO_CREATE_BUCKETS | Processor | Storage exclusivo | Não | Auto-create false; integração R2 a testar |
| FRONTEND_URL/BACKEND_URL/CORS_ORIGINS | Rails | Hosts novos validados | Não | Origens HTTPS explícitas |
| APP_URL/API_URL | Processor | Host API validado | Não | Sem localhost |
| EVO_AUTH_SERVICE_URL/EVO_AI_CORE_SERVICE_URL/BOT_RUNTIME_URL/BOT_RUNTIME_POSTBACK_BASE_URL | CRM | DNS internos reais | Não | Sem nomes presumidos entre stacks |
| EVO_AUTH_BASE_URL/EVOLUTION_BASE_URL/AI_PROCESSOR_URL/AI_PROCESSOR_VERSION | Core | Serviços internos | Não | v1; URLs auditadas |
| EVO_AUTH_BASE_URL/EVO_AI_CRM_URL/CORE_SERVICE_URL | Processor | Serviços internos | Não | Core já inclui /api/v1 |
| EVO_FLOW_ENABLED/API_URL/ALLOW_INSECURE | CRM/Sidekiq | Integração interna | Não | true; HTTP interno documentado, não Internet |
| MEDIA_HOST_ALLOWLIST | Bot Runtime | Hosts de mídia efetivos | Não | Restrita aos hosts validados |
| SMTP_*, MAILER_SENDER_EMAIL | Auth/CRM conforme config | Necessária para e-mail | PASSWORD sim | Desabilitado até credencial/destinatário autorizado |
| VITE_APP_ENV | Frontend build | Sim | Pública | staging |
| VITE_API_URL/AUTH_API_URL/EVOAI_API_URL/AGENT_PROCESSOR_URL/WS_URL | Frontend build | Sim; host gateway | Pública | Origin base; cliente anexa caminhos/WS |
| VITE_EVOFLOW_API_URL | Frontend build | Sim; campanhas | Pública | Pendente rota de gateway; não apontar indiscriminadamente ao CRM |

Esta matriz é o recorte operacional auditado, não catálogo exaustivo do produto.
Processor CORS está hardcoded `*` em src/main.py; CORS_ORIGINS não o corrige.
Validar CORS por serviço/gateway antes da publicação. Nenhuma VITE pode receber
segredo administrativo, credencial de banco ou chave de R2.
