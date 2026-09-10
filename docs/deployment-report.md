# Relatório de implantação — checkpoint de staging

## Atualização — 10/09/2026, avanço de banco e CI

**Estado atual:** conexão Supabase validada; schema EvoFlow migrado e runtime
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
