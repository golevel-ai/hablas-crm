# Supabase: validação e bootstrap limitado executados

Data: 10/09/2026. Projeto **hablas-crm**, ref `fizdiennudpyqrzmdukm`, organização
**Hablas** (`hnaujighizgevlmtkycw`), região us-east-1, plano Free, compute nano.
O responsável autorizou **um único projeto, com schemas separados**.

## Acesso comprovado

- MCP scoped/read-only usando OAuth já autorizado: URL do projeto confirmada;
  PostgreSQL 17.6, zero tabelas em public antes das mudanças, pgVector 0.8.2 disponível.
- Painel Connect: conexão direta `db.fizdiennudpyqrzmdukm.supabase.co:5432`, banco postgres,
  usuário administrativo postgres. Diretamente IPv6 por padrão; adicional IPv4 não contratado.
- Session Pooler: `aws-0-us-east-1.pooler.supabase.com:5432`, usuário administrativo
  `postgres.fizdiennudpyqrzmdukm`, banco postgres. Parâmetros obtidos do painel.
- Senha PostgreSQL recebida em diálogo local oculto; arquivo 0600 em diretório 0700
  ignorado pelo Git. Nenhum reset de senha ou uso das chaves Data API como senha.
- TLS e login reais passaram com node-postgres do lockfile EvoFlow. CA indicada
  pelo painel: infra/certs/supabase-root-2021.crt, SHA-256 do certificado
  `807025AD50D4ED219D2C9C7D299C004F824EB00CF7F65AFEF607D07B72E6CAFA`.

## Prova de isolamento local

PostgreSQL nativo **17.6**, descartável, ligado apenas a 127.0.0.1 e socket privado.
Empacotamento de teste embedded-postgres 17.6.0-beta.15; nunca usado como destino
da aplicação. Cluster encerrado/removido após o teste.

- 17 migrations EvoFlow aplicadas; segunda execução aplicou zero.
- Tabelas e enum homônimos colocados em public como sentinelas permaneceram intactos.
- Usuário de runtime conseguiu CRUD no schema EvoFlow e recebeu 42501 ao acessar
  tabela de public ou tentar criar tabelas.
- Cinco testes adicionais fizeram handshakes TLS locais: CA não confiável e hostname
  incorreto rejeitados; CA/hostname corretos aceitos; modos inseguros rejeitados.

## Mudanças remotas concluídas

Executor exclusivo com advisory lock de sessão; bootstrap somente em schema/roles
ausentes, sem CREATE DATABASE, sem schema load em public, sem iniciar aplicação.

| Recurso | Identidade |
|---|---|
| Schema EvoFlow | hablas_evoflow_staging, OID 17494 |
| Migration role | hablas_evo_stg_flow_migrator, OID 17490, limite 2 conexões |
| Runtime role | hablas_evo_stg_flow, OID 17492, limite 5 conexões |
| Marcador | hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9 |
| Extensão nova | pg_trgm no schema extensions |
| Migrations | 17, commit EvoFlow 1734849b8afa03aceda37122a083d2fad7216098 |

A migration que consultava catálogos sem escopo recebeu filtro de schema no overlay.
TypeORM usa schema e search_path próprios, `installExtensions=false`,
`synchronize=false`, `migrationsRun=false`. O build e o teste precederam o bootstrap.
Hash do conjunto JS de migrations testado:
`f813b4712ba94d61d98a40e0dea7eb42d4abf6a3225aeeffabe23ebe35b91e4b`.

## Verificação real de runtime

PASS via Session Pooler/TLS com a role hablas_evo_stg_flow:

- current_schema = hablas_evoflow_staging; OID coincide com manifesto.
- Permissões SELECT/INSERT/UPDATE/DELETE nas tabelas da aplicação: presentes.
- CREATE no schema: negado.
- SELECT em auth.users do Supabase: negado (consulta de privilégio, sem ler usuários).
- Acesso ao histórico de migrations: negado.
- Contacts novos: zero. Public: zero tabelas antes e depois.

## Pendências

Atualização: vector 0.8.2 foi habilitado em extensions. Foram criadas as roles
hablas_evo_stg_main_migrator (OID 17988, limite 3) e hablas_evo_stg_main
(OID 17990, limite 40), sem superuser/createdb/createrole, com marcador e senhas
próprios. Apenas grants de schema foram aplicados nesta preparação; o schema
principal continua aguardando bootstrap. O EvoFlow manteve OID/17 migrations.

Bootstrap principal Auth/CRM/Core/Processor, extensão vector para esse conjunto,
runtime role principal, Data API/grants de public antes de armazenar dados,
backup/restore e testes com todos os containers. Não classificar T03/T04 completos
nem o produto como implantado com base apenas nesta etapa EvoFlow.
