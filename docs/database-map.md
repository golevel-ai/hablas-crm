# Mapa de bancos — BLOCKED / PENDING_OWNER_INPUT

## Atualização — conexão comprovada e isolamento autorizado

Em 10/09/2026: projeto hablas-crm na organização Hablas, us-east-1, PostgreSQL 17.6.
O MCP mostrou apenas schemas internos com tabelas e zero tabelas em public; vector
0.8.2 está disponível, ainda não instalado. A CA indicada pelo painel foi registrada
em infra/certs/supabase-root-2021.crt. TLS e login administrativo PostgreSQL passaram
via `aws-0-us-east-1.pooler.supabase.com:5432`, banco postgres.

O responsável escolheu **um único projeto com schemas separados**. A divisão agora é:

| Schema | Consumidores | Isolamento |
|---|---|---|
| public | Auth/CRM/Sidekiq/Core/Processor | Preserva o compartilhamento do código; bootstrap principal ainda pendente |
| hablas_evoflow_staging | EvoFlow | Role e histórico TypeORM próprios; search_path sem public; runtime sem DDL |

A adaptação de configuração usa `schema` do TypeORM e `options=-c search_path=...`
do node-postgres. Uma migration consultava catálogos sem filtrar schema; o overlay
adiciona os filtros necessários. `installExtensions=false` impede DDL implícito
do driver no runtime. Teste local com PostgreSQL 17.6 aplicou 17 migrations, reaplicou
zero e preservou tabelas/tipos homônimos em public, com negação de acesso cruzado
e DDL para runtime. Não foi criado PostgreSQL local como substituto do Supabase:
o cluster era descartável de teste e foi encerrado/removido pelo ensaio.

As seções abaixo preservam a descoberta inicial. A preferência original por projeto
separado foi substituída pela decisão explícita acima.

Conexão PostgreSQL de runtime/migrations ainda não recebida ou testada. O responsável
já forneceu project ref, parâmetros da Data API e acesso MCP read-only autenticado.
Nenhum banco local criado.
Os nomes abaixo descrevem o código, **não bancos confirmados no destino**.

## Compatibilidade documentada

O guia oficial do Evo CRM Community, em **Passo 3 → Opção C — Banco de dados na
nuvem**, lista explicitamente **Supabase** entre os provedores compatíveis, com
pgVector nativo. Requisito documentado: PostgreSQL 16 ou superior + extensão vector.
Fonte conferida: https://docs.evolutionfoundation.com.br/self-hosted

Supabase permanece o PostgreSQL gerenciado escolhido para esta implantação.
As pendências deste mapa são a configuração e a validação do projeto concreto:
conexões PostgreSQL, TLS dos drivers do commit fixado, permissões, bootstrap e
isolamento EvoFlow. URL/chaves da Data API atendem outro método de acesso; o guia
do Evo solicita host, porta, banco, usuário e senha PostgreSQL.

| Domínio de dados | Serviços | Nome upstream / esquema | Runtime / migration role no destino |
|---|---|---|---|
| Principal compartilhado | Auth, CRM, ambos Sidekiq, Core, Processor | evo_community no desenvolvimento, evocrm no Swarm; public por padrão | Pendente: credenciais distintas com grants necessários |
| Fluxos/campanhas | EvoFlow | evo_campaign, banco dedicado; não se conecta diretamente ao schema CRM | Projeto Supabase separado preferencial, sujeito a autorização/custo |
| Eventos | EvoFlow → ClickHouse | evo_campaign.contact_events upstream | Usuário novo restrito e bootstrap do storage auditado |

Auth/CRM compartilham, entre outras, identidades/contas e dependem do schema mestre
CRM. Processor explicitamente exclui `users` de sua criação automática porque a
propriedade é do Auth. Os conjuntos completos de tabelas, FKs, extensions, RLS,
políticas e grants precisam de comparação estrutural antes do bootstrap.

## Executores reais descobertos

| Serviço | Caminho | Decisão para staging |
|---|---|---|
| CRM | Makefile seed-crm: db:create + db:schema:load; entrypoint db:prepare | Não usar em produção. Bootstrap vazio exige plano/schema mínimo verificado |
| Auth | db/migrate; entrypoint db:create/db:migrate; reconciliação RBAC | RUN_MIGRATIONS=false no runtime; executar tarefas necessárias sob lock único |
| Core | entrypoint.sh → migrate; evo_core_community_schema_migrations | Rodar migrator separadamente; runtime `/app/main`; DSN codificada corretamente |
| Processor | Alembic + scripts.run_seeders no CMD | Separar do Uvicorn, auditar seeds |
| Processor (extra) | src/main.py:225, Base.metadata.create_all no import | **Bloqueante**: remover/gatear DDL no boot e validar migrations equivalentes |
| EvoFlow | TypeORM dist/database/ormconfig.js; Compose cria DATABASE | Não executar CREATE DATABASE; migrar conexão real dedicada, TLS corrigido |
| ClickHouse | Inicialização do adaptador cria DB/tabelas IF NOT EXISTS | Auditar permissões; isto também é DDL no boot, não apenas health |

## TLS por driver

- Rails/libpq: POSTGRES_SSLMODE não é lida nos YAMLs. Validar `PGSSLMODE=verify-full`
  e `PGSSLROOTCERT` com CA no container, ou adaptar YAML explicitamente.
- Core: `DB_SSLMODE=verify-full`; conferir trust store/driver e CA específica.
- Processor: psycopg2/SQLAlchemy via `POSTGRES_CONNECTION_STRING`, `sslmode=verify-full`
  e caminho de CA quando necessário; password percent-encoded na DSN.
- EvoFlow: atualmente somente `POSTGRES_SSLMODE=require` ativa SSL, com
  `rejectUnauthorized:false`. `verify-full` **desativa** SSL nesse código.
  A correção de configuração é obrigatória antes de fornecer conexão ao processo.

Preferir conexão direta; Session Pooler se IPv4 exigir. Obter parâmetros do painel
Connect. Transaction Pooler não é padrão. CRM possui DB_PGBOUNCER, mas isso não
comprova compatibilidade dos outros consumidores/locks.

## Orçamento inicial, ainda não aplicado

Proposta: uma instância de cada API, Auth/CRM 3 threads cada, Sidekiq 3 cada,
Core 10 conexões, Processor um processo (SQLAlchemy padrão normalmente 5+10 overflow,
confirmar versão/consumidores adicionais), EvoFlow pool máximo 10 com parâmetro
correto do driver (`connectionLimit` atual precisa revisão). Base aproximada:
37 conexões máximas principal e 10 EvoFlow (47 no total), **antes** de engines adicionais,
administração, migrations e serviços internos Supabase. Não aprovar o orçamento
até medir e conferir limites reais do plano/projetos. Processos Rails/Puma extras
multiplicam pools; preencher WEB_CONCURRENCY explicitamente na configuração final.

## Condições para executar

1. Receber conexões corretas e confirmar projeto, região, TLS, roles e isolamento.
2. Mapear extension vector, schema/search_path e políticas já presentes; não alterar
   schemas internos Supabase. Validar Data API/grants/RLS sem criar políticas abertas.
3. Distinguir namespace de aplicação vazio de projeto Supabase sem objetos.
4. Comparar schema mestre/migrations; não marcar versões como aplicadas por conveniência.
5. Executor único com advisory lock de sessão mantido durante toda a operação,
   conexão direta/session e lock compartilhado entre todos os migrators. Trava
   de CI sozinha não impede execução administrativa concorrente.
6. Bootstrap explícito em namespace vazio; atualização incremental requer backup
   verificado. Falha interrompe promoção e nunca recarrega schema automaticamente.

Migrate/restore executáveis permanecem pendentes; criar scripts que executem o
Makefile atual seria inseguro. Próxima implementação deve começar pelos bloqueios
DDL/TLS e pela prova de equivalência de schemas, não por tentativa no banco real.
