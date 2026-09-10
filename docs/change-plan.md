# Plano de mudanças — staging

**Estado: dados e banco prontos; aplicação e frontend ainda não implantados.**
Destino exclusivo: VPS-US-VA-002-OP / 51.81.80.55 / UUID
`hwt9rmdg9rrodfb9hilh8vcn`, Coolify 4.3.18 em my.golevel.ai.
Cloudflare GoLevel / hablas.chat, IDs em `infra/environment.target.yml`.

## Estado dos recursos

### Dados Coolify — preflight renovado em 10/09/2026 04:56Z

Servidor/IP confirmados novamente, 9.629 MiB de memória disponível, 82 GB de disco
livre, onze containers existentes saudáveis e nenhum volume com prefixo hablas-evo.
Staging continua com zero recursos antes desta criação. Destino selecionado na UI:
server_id 5, destination `eolu061gu7rqdmd7umerbmuu`, correspondente ao UUID fixado.

O recurso Compose de dados foi criado com YAML materializado a partir das
configurações versionadas e digests verificados. O parser Compose 5.1.4 validou o
resultado. Credenciais finais estão vinculadas ao UUID e rotacionadas. Nenhum
domínio ou porta de host; limites de dados somam 2,5 GiB/1 CPU. UUID, volumes e
rede estão registrados em `docs/data-deployment.md`.

| Recurso | Nome/estado | Pré-condições |
|---|---|---|
| Projeto Coolify | hablas-evo-infra | Inventário de projetos completo, ausência de colisão |
| Ambiente | staging, dentro do projeto novo | Project UUID e marcador de propriedade |
| Compose dados | hablas-evo-data-staging | Digests, limites, volumes, rede, backup e capacidade aprovados |
| Compose aplicação | hablas-evo-app-staging | Supabase validado; bootstrap único concluído; imagens próprias |
| Worker | hablas-evo-frontend-staging | Build verificado; alocação completa; homologação restrita |
| DNS/hostname | Apenas o par de staging validado | Ausência de conflito revalidada; TLS isolado |
| R2 privado | hablas-evo-staging-media / hablas-evo-staging-backups | Criados privados; smoke de objetos passou; backup/restore real pendente |
| Volumes | hablas-evo-staging-redis/rabbitmq/clickhouse | Checagem de volumes e manifesto; jamais alterar nome em reexecução |

Não criar recursos automaticamente a partir desta tabela. IDs ausentes significam
ausência de recurso comprovado, não autorização para se apropriar de um homônimo.

## Histórico da criação isolada

Foram criados somente os metadados do projeto novo `hablas-evo-infra` e seu ambiente
`staging` na equipe autenticada `Go Team`, sem workloads ou cobrança. A consulta
de projetos às 22:48 America/Sao_Paulo mostrou quatro projetos, nenhum homônimo.
Marcador de propriedade novo:
`hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9`.
O marcador foi gravado na descrição e o UUID retornado foi registrado no manifesto.
O ambiente padrão criado pelo painel foi vinculado somente ao projeto novo e
renomeado para staging sem tocar em terceiros. Identidades e ausência do nome foram
revalidadas imediatamente antes do submit.

A primeira descrição usava `:` e `|`, rejeitados pelo ValidationPatterns da
versão 4.3.18 (código consultado no tag correspondente). Não houve redirect de
criação; revisar ausência de projeto antes de reenviar com descrição compatível.
O marcador acima usa somente caracteres permitidos, com o mesmo UUID aleatório.

## Escritas concluídas

09/09/2026 aproximadamente 22:55–22:57 America/Sao_Paulo:

1. Criado projeto `hablas-evo-infra`, UUID `jjxcrsedavkskvcbnuvmkaql`, descrição
   com marcador. O painel criou automaticamente um ambiente padrão vazio.
2. Registrado UUID `xukzvsnkjemq085zitdzzytf` no manifesto; confirmado vínculo e
   marcador do projeto por nova leitura. Renomeado esse ambiente para `staging`
   e adicionada descrição com o mesmo marcador, sem criar ambiente de produção real.
3. Nova leitura: cinco projetos (quatro anteriores + um novo), zero recursos no
   projeto novo; os cinco recursos existentes do servidor continuam saudáveis.

Manifesto operacional local: `infra/deployment-manifest.yml` (excluído do Git).
IDs não secretos também persistidos em target e deployment-report para retomada.
Não repetir criação por nome; reconciliar IDs + marcador. Não há volumes, rede,
container, Worker, DNS, bucket ou banco novo nesta execução.

## Sequência e travas

### Supabase — projeto staging dedicado concluído

O responsável autorizou usar o segundo projeto gratuito se isso não afetasse a
instalação. A documentação oficial confirma dois projetos ativos no Free Plan; o
painel confirmou Hablas/Free, spend cap ligado, nenhum método de pagamento e apenas
hablas-crm ativo. Foi criado hablas-evo-staging em us-east-1 como segundo projeto
incluído, sem addon, com Data API desativada. O projeto anterior não será alterado
nem limpo: migrations e roles de ensaio permanecem preservadas. Como o bootstrap
principal ainda não havia começado, todo runtime de staging foi reaplicado e
validado no novo project_ref antes de prosseguir.

### R2 — autorização posterior do responsável

O responsável autorizou criar hablas-evo-staging-media e hablas-evo-staging-backups,
privados e exclusivos, com credenciais separadas e uso sintético de homologação.
Foi informado que R2 cobra por uso após a franquia; nenhum addon foi autorizado.
A conta GoLevel/ID foi reconfirmada e o inventário tinha quatro buckets, sem esses
nomes. Usar locationHint enam quando aceito, registrar criação e conferir public
access desligado, sem custom domains. Tokens devem permitir somente objetos do
respectivo bucket. Nenhum bucket anterior será reutilizado ou alterado.

Após exposição operacional das primeiras credenciais, ambos os tokens foram
substituídos por novos tokens account-scoped de objetos, cada um limitado ao próprio
bucket. O smoke completo passou novamente e os tokens anteriores foram excluídos.

### Acesso principal Supabase — concluído

O ensaio CI 34438052395 passou no bootstrap nativo Auth/CRM e nos modelos
compartilhados, sem o comando de marcar migrations indiscriminadamente.
A escrita limitada criou as roles `hablas_evo_stg_main_migrator` e
`hablas_evo_stg_main`, com marcador do projeto e senhas exclusivas. Limites 3 e
40 conexões, sem SUPERUSER/CREATEDB/CREATEROLE; search_path public,extensions.
O migrator recebeu CREATE em public; runtime recebeu inicialmente apenas USAGE.
Vector foi habilitado em extensions. Depois, o bootstrap principal executou CRM,
Auth, Core, Alembic/Processor e seeds sob trava exclusiva, e aplicou os grants finais.
A verificação real confirmou 110 tabelas, CRUD permitido, DDL e acessos cruzados
negados, históricos protegidos e EvoFlow OID 17493/17 migrations intactos.

### CI e GHCR — autorização explícita posterior

O responsável autorizou branch/commit/push e build no GitHub Actions, com imagens
públicas no GHCR. Branch criada: infra/staging-deployment; primeiro commit b242527.
Run 34434439582 concluiu com sucesso: verificação + sete imagens.

Foi descoberto bloqueio real da organização golevel-ai: Public desmarcado nas
permissões de criação de packages; Private habilitado e Internal desmarcado.
Os pacotes novos foram inicialmente criados privados pelo GHCR. A tentativa de
cancelar o run encontrou-o já concluído; nenhum cancelamento ocorreu.

O responsável **autorizou explicitamente ajustar a política da organização**.
Mudança aprovada: habilitar Public em Package creation e tornar públicos somente
os sete packages hablas-evo-staging-{gateway,auth,crm,core,processor,bot,evoflow}
gerados por este run. Private, Internal e herança de acesso ficam com seus valores
observados. Essa autorização tem escopo GitHub; não altera a política global
Cloudflare, DNS ou Coolify. Conferir pull anônimo de cada digest após a alteração.

### Histórico — decisão anterior substituída pelo projeto dedicado

Naquele checkpoint, o responsável escolheu **usar somente o projeto atual**, autorizando avaliar/testar
schemas separados. Projeto verificado: `fizdiennudpyqrzmdukm`, hablas-crm, organização
Hablas (`hnaujighizgevlmtkycw`), us-east-1, Free. Login PostgreSQL administrativo
via Session Pooler passou com CA/hostname verificados; senha recebida por diálogo
local oculto e armazenada fora do Git com modo 0600.

Recursos exatos a criar pelo bootstrap EvoFlow, após nova checagem de ausência:

- Schema `hablas_evoflow_staging`, com comentário contendo o marcador do manifesto.
- Roles `hablas_evo_stg_flow_migrator` (limite 2 conexões) e
  `hablas_evo_stg_flow` (limite 5), senhas próprias, sem CREATEDB/CREATEROLE/SUPERUSER.
- Extensão pg_trgm em `extensions`, se ausente, necessária às migrations existentes.
- As 17 migrations TypeORM do commit fixado **apenas no schema novo**; nenhum
  CREATE DATABASE, novo projeto, mudança em auth/storage/vault ou schema load no public.
- Grants da aplicação restritos ao schema EvoFlow, sem DDL para runtime; sem acesso
  runtime à tabela de histórico de migrations. Referências/IDs ficam no manifesto.

Antes da escrita: prova local PostgreSQL 17.6, credencial/TLS validados, schema/roles
ausentes, public ainda sem tabelas, advisory lock exclusivo. Erro bloqueia promoção
e preserva recursos para inspeção; não há rollback destrutivo nem upsert de homônimos.
Após a escrita: conferir migrations, OIDs/marcador, ausência de alterações no public,
login/limites/grants do runtime. A aplicação continua sem ser iniciada.

Executor: `scripts/ops/bootstrap_evoflow.cjs`, com `--target`, contexto testado e
`--dry-run`/`--apply` explícitos. Reexecução sobre recursos existentes exige
reconciliação pelo manifesto; não tenta recriá-los ou recarregar schema.

1. Fixar código/submódulos, auditar configuração e testar build local.
2. Completar baseline e alocação; registrar proteção de cookies, Access e TLS.
3. Definir registry, digests e limites; validar Compose normal no runtime do Coolify.
4. Validar conexões Supabase fornecidas e mapa de bancos, sem fallback local.
5. Registrar manifesto privado com marcador estável de propriedade; criar apenas
   recursos novos validados e autorizados. Antes de **cada** escrita conferir IDs,
   ambiente e disponibilidade dos nomes. Compare baseline após cada alteração.
6. Migrar com executor único, timeout e lock compartilhado; erro bloqueia deploy.
7. Deploy pelo Coolify, frontend pelo Wrangler com account explícito. Sem execução
   paralela de `docker compose up` sobre os mesmos recursos.
8. Testes funcionais/operacionais, backup/restore e rollback em ambientes isolados.

Os scripts de preflight entregues são de leitura; ainda não existe autorização
automatizada para provisionamento. Marcar todas as pendências no relatório.
Reversão futura somente do recurso novo causador do impacto, identificado por ID
e marcador; preservar volumes e dados. Promoção de produção exige plano posterior.
