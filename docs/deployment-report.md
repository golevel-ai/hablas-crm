# Relatório de implantação — checkpoint de staging

## Estado mais recente — execução staging/final autorizada

O responsável escolheu `crm.hablas.chat` para o frontend final,
`api-crm.hablas.chat` para a API final e confirmou fresh start: usuários, histórico,
mídia e configurações do fornecedor anterior não serão importados. A autorização
vigente passou a `FULL_STAGING_AND_FINAL_DEPLOYMENT_AUTHORIZED`; staging, aplicação
Coolify, DNS/Workers e publicação final estão autorizados em sequência controlada.

Às 17:37 UTC de 10/09/2026, consultas read-only autenticadas à Cloudflare confirmaram
zero registros DNS e zero Workers Custom Domains para `crm.hablas.chat`,
`api-crm.hablas.chat`, `evo-stg.hablas.chat` e `evo-api-stg.hablas.chat`. O e-mail e
DKIM sob `crm.hablas.chat` permanecem preservados. O CI do HEAD remoto `e18d520`
passou no run 34483306076.

Localmente, o Gate A agora inclui build frontend com sete origens staging,
Worker Static Assets com CSP/headers e bloqueio de rotas backend, ambientes Wrangler
staging/production sem domínio ativo, manifesto SHA-256 do dist, Auth HTTPS/HSTS e
ActiveStorage R2 priorizando ambiente, gateway com CORS exato e rota de campanhas,
além de testes e guardas preparados para CI. O build passou localmente em Node
20.20.0; testes Worker e dry-runs Wrangler passaram em Node 22.19.0. O workflow
separa as duas toolchains e condiciona upload/GHCR à autorização remota, agora ativa.
A revisão independente final não encontrou bloqueios altos ou médios. Docker/actionlint
local continuam indisponíveis; CI remoto é a próxima prova;
a release implantável permanece `38e99df` até a conclusão do CI agora autorizado.

## Base existente — dados e banco principal prontos

R2 atualizado: buckets privados hablas-evo-staging-media e hablas-evo-staging-backups
criados na conta GoLevel, ENAM/Standard, sem r2.dev nem custom domains habilitados.
Tokens de conta separados, restritos a objetos do respectivo bucket, foram gerados
e guardados localmente em arquivos 0600, sem valores em logs/Git. Backup real e
restauração ainda não foram testados. Release 38e99df passou no CI 34446396309; os sete novos digests
foram verificados por acesso anônimo e o candidato anterior foi arquivado.

Atualização Supabase: a organização Hablas está no Free Plan, spend cap ligado,
sem método de pagamento, e tinha um projeto ativo. Com autorização posterior do
responsável, hablas-evo-staging (`znxlfqctnezrropcbftw`) foi criado como o segundo
projeto incluído, us-east-1/nano, sem addon e com Data API e chaves JWT legadas
desativadas. O segredo legado observado no diagnóstico foi revogado antes de uso.
Login/TLS, PostgreSQL 17.6 e baseline public vazio foram comprovados. EvoFlow foi
reaplicado no projeto dedicado (17 migrations, runtime isolado). O bootstrap
principal Auth/CRM/Core/Processor e seeds foi concluído sob host flock e advisory
lock PostgreSQL, seguido dos grants de runtime.

O smoke R2 enviou e leu 64 KiB sintéticos em cada bucket, conferiu checksum e URL
assinada, negou acesso anônimo pelo endpoint S3 e negou cada credencial no bucket
oposto. O painel confirmou `r2.dev` e custom domains desativados. Objetos de teste
foram removidos; somente os marcadores de propriedade foram preservados.

- **Implantado/testado:** hablas-evo-data-staging no servidor correto. Redis,
  RabbitMQ e ClickHouse healthy, limites reais confirmados, sem domínio/portas de host.
  UUID nrvbltvkzmzvivrbkldjok6y; volumes/rede em data-deployment.md.
- **Banco:** EvoFlow e principal migrados. A role principal real passou via TLS com
  110 tabelas, CRUD, sem DDL, sem acesso a auth.users/EvoFlow e sem escrita nos históricos.
- **CI:** run 34461735871 passou no bootstrap Rails nativo e nos modelos
  compartilhados. As diferenças entre dumps não foram mascaradas por history-stamping.
- **Processor:** Alembic e ADK usam opções nativas asyncpg com SSLContext e verificação
  completa. O runner explícito foi comprovado no banco real; o probe ADK foi removido.
- **Segredos:** após a última exposição operacional, todos os valores presentes no
  Coolify foram rotacionados novamente. A chave Fernet tem 32 bytes em Base64 URL
  com padding; 31 valores, serviços de dados e credencial migradora foram validados.
  Os dois tokens R2 também foram substituídos após exposição de cópias baixadas; os
  anteriores foram excluídos, os substitutos repetiram o smoke e as cópias foram removidas.
- **Aplicação e frontend:** ainda não implantados. Fresh start/setup/admin,
  backups/restore e testes funcionais continuam pendentes.
- **Domínios:** a revisão autenticada confirmou o CRM white-label anterior em
  crm.hablas.chat. O responsável liberou o subdomínio removendo o CNAME; às 15:13
  UTC ele não tinha CNAME/A/AAAA, não resolvia publicamente e ainda não estava
  vinculado a Worker. `api-crm` e `lp.crm` também foram removidos; o CNAME de
  e-mail e o DKIM permanecem preservados. `docs/crm-cutover-plan.md` registra os
  gates de homologação, fresh start, GO e rollback antes de usar o host liberado.

Os checkpoints anteriores abaixo são históricos; esta seção e os documentos de
evidência por componente representam o estado atual.

## Histórico — 10/09/2026, avanço inicial de banco e CI

**Estado naquele checkpoint:** conexão Supabase validada; schema EvoFlow migrado e runtime
verificado; aplicação completa ainda não implantada. Esta seção atualiza o
checkpoint inicial preservado abaixo.

- Projeto hablas-crm/Hablas/us-east-1, PostgreSQL 17.6, confirmado por MCP e painel.
- Senha recebida por diálogo oculto local e login TLS real aprovado; sem reset.
- Escolha explícita do responsável: um projeto Supabase com schemas separados.
- 17 migrations EvoFlow testadas localmente em PostgreSQL 17.6; reexecução com zero
  migrations; sentinelas public preservadas, acesso cruzado e DDL de runtime negados.
- Mesmo bootstrap aplicado em hablas_evoflow_staging (OID 17494); roles próprias
  OIDs 17490/17492; runtime real via TLS testado. Public permaneceu com zero tabelas.
- Compose app de nove processos criado; ambos Composes passaram em Docker Compose
  standalone 5.1.4 (`config --no-interpolate --quiet`), sem daemon/banco local de produção.
- Doze manifests OCI linux/amd64 resolvidos e verificados por SHA-256 em
  infra/build/oci.lock.json; imagens próprias ainda dependem do build CI.
- Contextos de build derivados dos commits fixados com overlays: TLS Rails/EvoFlow,
  cookies host-only e nomes próprios, boot sem migrations nos processos Rails,
  sem create_all no import do Processor, pool limitado, sem auto-criação de bucket,
  rota campaigns e CORS de origens exatas no gateway. Submódulos preservados.
- Build EvoFlow ajustado e cinco testes TLS passaram; 13 testes de guardas passam.
- CI/branch/commit/push e publicação de imagens públicas no GHCR autorizados pelo
  responsável. Workflow de build preparado; publicação/execução a registrar após confirmação.
- Frontend de clientes solicitado: **crm.hablas.chat**. CNAME existente exige
  revisão na etapa de publicação; nenhum domínio foi alterado nesta retomada.

Evidência detalhada: `docs/supabase-validation.md`. Manifesto real e senhas ficam
fora do Git. Próxima etapa: executar CI autorizado, auditar/testar bootstrap principal
e completar recursos de dados/R2, alocação e proteção dos hosts antes de iniciar a aplicação.

### CI concluído e próxima prova de bootstrap

O commit b242527 foi enviado para infra/staging-deployment. Run 34434439582 terminou
success, incluindo as sete imagens. Após autorização explícita do responsável,
a política GitHub Public foi habilitada e apenas os packages desta implantação
foram publicados. Os sete digests passaram em verificação de acesso anônimo e
hash/plataforma/proveniência; registros importados em versions.lock.yml.
Detalhes: build-publication.md.

A comparação estática dos dumps Rails encontrou 16 tabelas Auth compartilhadas
dentro de 88 tabelas CRM, com cinco divergências: defaults de created_at/updated_at
em installation_configs e PK/nullability/FK de user_tours. **Não foi usado o comando
upstream de marcar todas as migrations Auth como aplicadas.** Um teste isolado de
bootstrap principal e modelos cruzados está sendo acrescentado ao CI para verificar
o caminho nativo de migrations antes de qualquer schema load no Supabase principal.

**Data:** 09/09/2026, encerramento deste checkpoint aproximadamente 23:10
America/Sao_Paulo (10/09/2026 UTC).
**Estado:** preparação parcial + metadados de staging configurados.
**Aplicação implantada:** não. **Pronto para implantação completa:** não.
**Pronto para produção:** não. Retomar após reiniciar OpenCode para carregar o MCP.

## Resultado efetivo

| Dimensão | Evidência |
|---|---|
| Código | Fork informado `https://github.com/golevel-ai/hablas-crm.git`, main fixada em `fa6924df23b863de30b065d25e301bb414593bd5` |
| Submódulos | 10 diretos + whatsmeow-lib recursivo, commits fixados inicializados; nenhuma atualização por branch |
| Destino | VPS-US-VA-002-OP / 51.81.80.55, UUID `hwt9rmdg9rrodfb9hilh8vcn`, confirmado no cadastro e no host |
| Coolify | 4.3.18, equipe Go Team; projeto novo `jjxcrsedavkskvcbnuvmkaql` |
| Ambiente | staging, UUID `xukzvsnkjemq085zitdzzytf`; zero recursos |
| Propriedade | `hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9`, gravado nas descrições e manifesto |
| Cloudflare | GoLevel `85354ee4fc8d1c079a66f6321a5c78c5`; zona hablas.chat `b0a4153d93f81cd7957e34cdfcd11e60` |
| Domínios | Nenhum alocado/publicado; candidatos staging sem DNS exato na amostra; `evo.hablas.chat` ocupado |
| Supabase | Ref fornecida `fizdiennudpyqrzmdukm`; MCP configurado read-only e OAuth autenticado; projeto/schema/conexões PostgreSQL ainda não validados |
| Dados/filas/mídia | Nenhum banco, volume, container, fila ou bucket novo criado |
| Backups/restore | Não executados; destino independente e ambiente de recuperação pendentes |
| Git remoto | Nenhum commit/push/PR executado |

URL do staging administrativo:
https://my.golevel.ai/project/jjxcrsedavkskvcbnuvmkaql/environment/xukzvsnkjemq085zitdzzytf

## Arquivos entregues

- `.gitignore`: exclui evidências brutas, secrets/runtime envs e artefatos operacionais.
- `opencode.json`: MCP Supabase com project_ref e read_only, sem segredo.
- `infra/environment.target.yml`, `infra/versions.lock.yml`,
  `infra/deployment-manifest.example.yml`; manifesto operacional real local ignorado
  em `infra/deployment-manifest.yml`.
- `infra/coolify/compose.data.yml`, `env.data.example`: proposta Redis/RabbitMQ/
  ClickHouse com persistência, autenticação obrigatória, limites, logs e sem portas.
- `infra/redis/redis.conf`, `infra/rabbitmq/rabbitmq.conf`,
  `infra/clickhouse/config-overrides.xml`.
- `infra/cloudflare/wrangler.jsonc`, `env.frontend.example`, package.json/lock com
  Wrangler 4.130.0, assets SPA, sem workers.dev/preview/hostname ativo.
- `scripts/ops/ops.py`, `validate.sh`, `preflight.sh`, `preflight-domain.sh`,
  `test_ops.py`: leitura/validação, destinos explícitos, timeouts, paginação,
  erros sanitizados e bloqueio de publicação/migrations.
- Documentos: architecture-current, architecture-target, deployment-inputs,
  existing-environment-baseline, domain-allocation, change-plan, environment-matrix,
  database-map, deploy-coolify, deploy-cloudflare, backup-restore, rollback e este relatório.

## Preparação ainda não entregue como executável

`compose.app.yml`/`env.app.example`, geração final dos headers/rotas frontend,
build/publicação de imagens, executor único de migrations/deploy, `smoke.sh`,
`backup.sh` e `restore.sh` permanecem pendentes. Não há scripts vazios ou que
simulem sucesso. Não criar definitions RabbitMQ fictícias: depende da topologia
real auditada. Os limites atuais são propostas, não limites observados no runtime novo.

## Validações executadas

| Verificação | Resultado / escopo |
|---|---|
| git status/rev-parse/submodule status | PASS: fonte fixa, gitlinks correspondentes; alterações novas locais de infra/documentação |
| Inicialização submódulos | Primeiro timeout 120s; retomada com 600s concluiu os commits fixados |
| Frontend npm ci | PASS usando package-lock original; lock não atualizado |
| Frontend npm run build | PASS: TypeScript + Vite 6.4.2, Node 26.7.0/npm 11.19.0; URLs api.build.invalid, **não publicável** |
| Frontend testes selecionados | PASS: 60 testes/3 arquivos campaigns, journeys, segments; HTTP mockado, não E2E |
| Guardas operacionais | PASS: 13 testes unittest, sem rede/banco; identidade errada, política relaxada, domínio pai/wildcard, paginação incompleta/repetida e falta de permissão/token bloqueiam |
| validate/preflight local | PASS: política/destino/gitlinks; não prova Compose runtime nem segredo efetivo |
| preflight --stage remote | BLOCKED esperado, código 2 na execução real, sem conexão de banco ou escrita remota |
| preflight-domain --dry-run | NOT_EXECUTED: somente plano GET; código 0 não significa host livre |
| CLI preflight-domain real | BLOCKED: token CLI ausente; inventário remoto feito separadamente na sessão web autenticada |
| YAML/JSON/XML + bash -n + diff --check | PASS nos arquivos preparados; Docker Compose não executado localmente (Docker ausente) |
| Wrangler deploy --dry-run | PASS, Wrangler 4.130.0, 67 assets lidos; nenhum upload/deploy real |
| MCP Supabase | Configuração aceita pelo CLI; comando literal ausente, npx alternativo concluiu OAuth após primeiro timeout. Ferramentas exigem reinício da sessão |
| Preservação | 47 registros DNS idênticos por SHA-256; cinco workloads anteriores saudáveis; raiz/app 200 antes/depois; www 301 em nova leitura |

Warnings do build: chunks grandes e módulos simultaneamente estáticos/dinâmicos;
nenhuma otimização de produto realizada. npm 11 informou scripts de instalação
não aprovados em dependências, mas build frontend e Wrangler dry-run concluíram.
Não foi demonstrada equivalência da toolchain local com Node 20 do Dockerfile.

## Critérios PRD T01–T23

Os status abaixo avaliam **o requisito completo**, não apenas subchecks locais.
Ambiente: staging proposto; release: commit acima; evidências desta sessão em docs.

| ID | Resultado | Evidência / bloqueio |
|---|---|---|
| T01 | BLOCKED | Parsing e guardas passam; faltam Compose app, validação Compose runtime e secrets efetivos |
| T02 | BLOCKED | Gitlinks fixados; imagens próprias/digests ainda ausentes |
| T03 | BLOCKED | Conexões PostgreSQL/TLS/roles não recebidas/validadas |
| T04 | BLOCKED | Bootstrap compartilhado não validado; DDL automático Processor descoberto |
| T05 | BLOCKED | Nenhuma API/admin/setup implantado |
| T06 | BLOCKED | Sem banco/backend; persistência CRM não testada |
| T07 | BLOCKED | R2 exclusivo/credenciais/fluxo artifacts pendentes |
| T08 | BLOCKED | Compilação passa; bundle de auditoria inválido para publicação; headers/SPA/API/login não testados |
| T09 | BLOCKED | Clientes possuem 60 testes passando; gateway campaigns/WS integrado pendente |
| T10 | BLOCKED | Redis/Sidekiq novos ausentes; reinício/job em execução não testados |
| T11 | BLOCKED | Broker novo ausente; nenhuma pausa de 60 minutos executada |
| T12 | BLOCKED | EvoFlow/ClickHouse não implantados; persistência/consulta pendentes |
| T13 | BLOCKED | Access do Coolify observado; auditoria externa de portas/proteções incompleta |
| T14 | BLOCKED | Sem credenciais/destinatários SMTP/canal/IA de teste validados |
| T15 | BLOCKED | Alertas novos não configurados/testados |
| T16 | BLOCKED | Nenhum backup/restore independente ensaiado |
| T17 | BLOCKED | Nenhuma release anterior nova implantada para ensaio |
| T18 | BLOCKED | Apenas capacidade pontual medida; nenhuma carga sintética |
| T19 | PASS | Conta/zona/servidor/host confirmados por IDs reais e IP |
| T20 | BLOCKED | DNS e recursos CF inventariados; análise completa de domínios/proxy/cookies/regras ainda pendente |
| T21 | BLOCKED | DNS e workloads preservados na comparação; cobertura incompleta dos endpoints/sessões atuais |
| T22 | PASS | Guardas bloqueiam Supabase pendente; nenhum bootstrap/produção/fallback local ou banco alheio executado |
| T23 | BLOCKED | Cookies hardcoded/legados e CORS Processor exigem adaptação e auditoria do domínio pai |

## Próxima ação exata

1. **Encerrar e reiniciar OpenCode neste diretório** para carregar o MCP Supabase
   já autenticado. Manter `read_only=true` e limitar a consulta à ref informada.
2. Confirmar nome/organização/região/status do projeto, schemas/tabelas/extensions
   existentes e se é o principal desta implantação. Não inferir projeto vazio
   nem usar secret Data API como DSN; não alterar objetos internos Supabase.
3. Completar mapa de banco e conexões PostgreSQL de runtime/migration via cofre,
   inclusive decisão do EvoFlow. Chave secreta enviada no chat deve ser revogada
   pelo responsável; seu valor não foi persistido nos arquivos do projeto.
4. Corrigir/gatear DDL no import do Processor, TLS EvoFlow, CORS/cookies e rota
   campaigns; validar bootstrap em ambiente descartável explicitamente autorizado.
5. Finalizar imagens linux/amd64/digests e Compose app, revisar limites completos,
   alocação/Access/TLS por hostname e backup independente. Retomar recursos **pelos
   UUIDs e marcador do manifesto**, sem criar outro projeto.

Sem esses passos, manter o ambiente administrativo vazio e o preflight remoto
bloqueado. A configuração de MCP/API não comprova funcionamento do Evo.

## Atualização de execução — 10/09/2026 18:47 UTC

O relatório acima preserva a fotografia anterior. Depois dela, a release imutável
`425658c25a03f74a232098d4323c0ceb24463fa6` passou no CI, foi implantada no Coolify
e os nove containers ficaram healthy. O bootstrap criou um único super-admin e a
segunda chamada foi recusada. Core TLS e o acesso somente leitura do runtime EvoFlow
à metadata de migrations foram validados.

Os hosts `evo-stg.hablas.chat` e `evo-api-stg.hablas.chat` foram publicados usando
somente recursos Cloudflare já ativos. Nenhum plano/add-on foi habilitado; Access
permanece inativo por decisão do responsável. Passaram TLS, health, CORS/preflight,
negação 403 de origem não aprovada, login/validate/refresh/logout, dashboard e APIs
autenticadas, setup-lock, navegação SPA, bloqueio de backend no host frontend e
ActionCable 101 com welcome/ping.

Isso atualiza T01–T05 e o escopo navegador de T08/T09, mas não fecha o requisito
completo. Backup/restore, reset de senha/SMTP, mídia após restart, canais,
integrações, rollback, carga e aceite de negócio continuam bloqueando o GO final.

## Atualização de execução — 10–11/09/2026: bump do CRM para o tip do develop

A pedido do responsável, o submódulo `evo-ai-crm-community` avançou de `aa3d408`
(v1.1.0) para `4083ddd` (tip de `origin/develop`, 56 commits acumulados). Não
temos permissão de escrita em `evolution-foundation/evo-ai-crm-community`
(confirmado via API: `push:false`); este avanço só move nosso ponteiro local, não
mescla `develop` em `main` naquele repositório. `db/schema.rb` ficou byte-idêntico
entre os dois commits — as três migrations tocadas foram refatoradas para um
helper `ConcurrentIndexMigration` compartilhado, sem alterar o resultado final do
schema — então nenhuma migração de banco foi necessária. Também não houve
mudança de Gemfile nem de variável de ambiente nova.

O CI (`build-staging.yml`, run `34548070889`) reconstruiu as sete imagens da
release. Na primeira tentativa (run `34547822953`) o job `verify` falhou com
`BLOCKED: Application tree changed relative to the locked fork`: `validate_release()`
em `scripts/ops/ops.py` nunca havia processado um bump de submódulo antes e tratava
o próprio caminho do submódulo como uma mudança de árvore não permitida, mesmo com
`infra/versions.lock.yml` e o commit do submódulo já coerentes entre si. Corrigido
permitindo correspondência exata aos caminhos declarados em
`lock["submodules"]`; os dois controles seguintes na mesma função (conjunto
recursivo de submódulos igual ao lock; HEAD de cada submódulo igual à revisão
travada, sem alterações locais) continuam obrigatórios e não foram enfraquecidos.
Reproduzido e corrigido localmente antes do reenvio; a segunda execução do CI
passou.

`scripts/ops/import_release.py` bloqueava qualquer substituição de release quando
já existe `app_uuid` no manifesto — comportamento correto para o fluxo anterior à
implantação, mas sem caminho para **promover uma imagem nova a uma aplicação já
publicada**. Adicionada a flag explícita `--update-deployed-application`, que só
libera essa substituição quando combinada com `--replace-candidate`; a release
anterior (`425658c`) foi arquivada automaticamente em
`infra/releases/425658c25a03f74a232098d4323c0ceb24463fa6.json`. As sete imagens
foram verificadas por digest público linux/amd64 no GHCR antes da gravação.

Rollout aplicado: `CRM_IMAGE` atualizado no Coolify e `Restart (pull latest)`
executado; os nove containers foram recriados e ficaram `healthy`. Confirmado por
dentro do container em execução que `lib/concurrent_index_migration.rb` existe
(arquivo novo do commit `4083ddd`), comprovando que o runtime está no build novo,
não apenas o valor da variável de ambiente. Nova aceitação em staging passou:
login, `validate`, dashboard e chamadas autenticadas, logout, e handshake
ActionCable 101. `infra/versions.lock.yml.image_status` está
`PUBLISHED_APPLICATION_IMAGES_VERIFIED_DEPLOYED_TO_STAGING`.

Observação operacional: durante esta janela, `my.golevel.ai` ficou temporariamente
inacessível para este executor devido à regra de firewall "REGRA VPN" da zona
`golevel.ai` (bloqueia todo acesso exceto a partir de quatro IPs cadastrados). Isso
não foi contornado nem a regra foi alterada; o responsável reconectou a VPN para
restaurar o acesso a partir de um IP já autorizado.
