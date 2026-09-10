# Plano de mudanças — staging

**Estado: projeto/ambiente vazios criados; workloads não implantados.**
Destino exclusivo: VPS-US-VA-002-OP / 51.81.80.55 / UUID
`hwt9rmdg9rrodfb9hilh8vcn`, Coolify 4.3.18 em my.golevel.ai.
Cloudflare GoLevel / hablas.chat, IDs em `infra/environment.target.yml`.

## Recursos propostos, sujeitos a preflight

### Dados Coolify — preflight renovado em 10/09/2026 04:56Z

Servidor/IP confirmados novamente, 9.629 MiB de memória disponível, 82 GB de disco
livre, onze containers existentes saudáveis e nenhum volume com prefixo hablas-evo.
Staging continua com zero recursos antes desta criação. Destino selecionado na UI:
server_id 5, destination `eolu061gu7rqdmd7umerbmuu`, correspondente ao UUID fixado.

Criar o recurso Compose de dados com o YAML público materializado a partir das
configurações versionadas e digests verificados. SHA-256 do YAML enviado:
`182ae9dd64cfdc3aea3a15f55d88b45a86168020ef8b4dbb490d83a07047ffbb`.
O parser Compose 5.1.4 validou o resultado. Credenciais serão geradas uma vez e
vinculadas ao UUID retornado antes do primeiro start. Nenhum domínio ou porta de
host; limites novos de dados somam 2,5 GiB/1 CPU. Registrar UUID/volumes/rede e
revalidar os recursos anteriores após a implantação.

| Recurso | Nome proposto | Pré-condições |
|---|---|---|
| Projeto Coolify | hablas-evo-infra | Inventário de projetos completo, ausência de colisão |
| Ambiente | staging, dentro do projeto novo | Project UUID e marcador de propriedade |
| Compose dados | hablas-evo-data-staging | Digests, limites, volumes, rede, backup e capacidade aprovados |
| Compose aplicação | hablas-evo-app-staging | Supabase validado; bootstrap único concluído; imagens próprias |
| Worker | hablas-evo-frontend-staging | Build verificado; alocação completa; homologação restrita |
| DNS/hostname | Apenas o par de staging validado | Ausência de conflito revalidada; TLS isolado |
| R2 privado | hablas-evo-staging-media (proposta) | Disponibilidade, propriedade, custo e credencial exclusiva |
| Volumes | hablas-evo-staging-redis/rabbitmq/clickhouse | Checagem de volumes e manifesto; jamais alterar nome em reexecução |

Não criar recursos automaticamente a partir desta tabela. IDs ausentes significam
ausência de recurso comprovado, não autorização para se apropriar de um homônimo.

## Próxima escrita autorizada e isolada

Criar somente os metadados do projeto novo `hablas-evo-infra` e seu ambiente
`staging` na equipe autenticada `Go Team`, sem workloads ou cobrança. A consulta
de projetos às 22:48 America/Sao_Paulo mostrou quatro projetos, nenhum homônimo.
Marcador de propriedade novo:
`hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9`.
Gravar esse marcador na descrição e registrar UUID retornado no manifesto antes
de criar o ambiente. Se o painel criar um ambiente padrão, ele pertence somente
ao projeto novo; registrar seu ID e ajustar para staging sem tocar em terceiros.
Revalidar as identidades e a ausência do nome imediatamente antes do submit.

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

### Acesso principal Supabase — preparação autorizada pela implantação

O ensaio CI 34438052395 passou no bootstrap nativo Auth/CRM e nos modelos
compartilhados, sem o comando de marcar migrations indiscriminadamente.
Próxima escrita limitada: criar roles novas `hablas_evo_stg_main_migrator` e
`hablas_evo_stg_main`, com marcador do projeto e senhas exclusivas. Limites 3 e
40 conexões, sem SUPERUSER/CREATEDB/CREATEROLE; search_path public,extensions.
O migrator recebe CREATE em public; runtime recebe apenas USAGE até os grants
de tabelas posteriores. Habilitar vector em extensions, sem alterar tabelas
existentes. Conferir public ainda vazio e EvoFlow OID 17494/17 migrations intactos
sob a mesma trava de sessão. Nenhum schema load nesta operação.

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

### Supabase — decisão posterior e próximo bootstrap limitado

O responsável escolheu **usar somente o projeto atual**, autorizando avaliar/testar
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
