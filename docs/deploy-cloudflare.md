# Runbook frontend Workers — publicação autorizada por gates

Conta GoLevel confirmada; IDs no target e Wrangler. O bloco principal representa
staging e `env.production` reserva o nome final; nenhum deles contém rota, Custom
Domain, workers.dev ou preview URL público. Nenhum Worker foi criado. Wrangler
4.130.0 usa Node 22.19.0 no CI; o build frontend permanece em Node 20.20.0.

## Inventário

```bash
bash scripts/ops/preflight-domain.sh --target infra/environment.target.yml --dry-run
# Com CLOUDFLARE_API_TOKEN autorizado injetado pelo cofre no ambiente:
bash scripts/ops/preflight-domain.sh --target infra/environment.target.yml --report docs/domain-allocation-next.md
```

GETs autenticados verificam conta/zona, DNS/paginação, rotas, custom domains,
Workers, Pages, Tunnel ingress, Load Balancers, Access e detalhes de rulesets.
O relatório novo nunca sobrescreve o anterior e tem modo 0600; revisar e consolidar
a evidência sanitizada em domain-allocation.md. Saída 2 é esperada para
REVIEW_REQUIRED/BLOCKED; ausência de conflito DNS não é sucesso de publicação.

O inventário via navegador já foi realizado parcialmente. O script CLI não importa
a sessão web; precisa de token autorizado com leitura dos produtos relevantes.
Falta de leitura de uma categoria bloqueia o inventário automatizado.

## Build auditado

Gerenciador selecionado por Dockerfile: npm e package-lock.json (há também pnpm lock,
não foi usado). O build TypeScript + Vite local concluiu com Node 20.20.0 e todas as
origens em `evo-api-stg.hablas.chat`; o scanner não encontrou placeholder, `.invalid`
ou localhost API ativo. CI ainda precisa reproduzir e publicar o dist + manifesto
SHA-256 como artefato imutável antes de qualquer deploy.

O cliente acrescenta `/api/v1`; ActionCable converte a origem e acrescenta `/cable`.
Não repetir sufixos. VITE_EVOFLOW_API_URL continua necessária para campaignsService;
sem adaptação do gateway ela não pode ser substituída silenciosamente pela URL CRM.
VITE_CAMPAIGN_API_URL também é obrigatória: ela gera URLs públicas de trigger de
jornada e seu fallback upstream é `localhost:3000`.

O manifesto SHA-256 cobre cada arquivo de `dist` e também `worker.mjs` e
`wrangler.jsonc`; o upload remoto do artefato e a publicação GHCR permanecem
condicionados a `remote_changes_authorized`; a autorização agora está ativa para a
sequência staging/final aprovada.

## Antes da publicação

1. Resolver os bloqueios de domain-allocation.md e definir Access restrito do
   frontend antecipado. Não liberar API/setup incompleto nem canais de produção.
2. O Worker local agora aplica nosniff/CSP e política distinta de embedding para
   `/widget`; `https:`/`wss:` permanecem necessários para integrações e dashboards
   configuráveis. Validar a política contra integrações reais antes da publicação.
3. O Worker rejeita caminhos backend no host frontend antes do fallback SPA;
   manter o teste de contrato para que requisições JSON nunca recebam HTML.
4. Conferir bundle: nenhuma VITE placeholder, credencial, URL privada ou `.invalid`
   ativa. Fallbacks localhost literais existem no código, exigem revisão de uso efetivo.
5. Validar Wrangler local, escolher apenas o hostname novo como custom domain e
   revalidar conta/Worker/nome antes de criar. Sem rotas wildcard abrangentes.
6. Deploy backend + login/logout/refresh, navegação direta, mídia, OAuth quando
   habilitado, WS reconnect. Apenas HTML renderizado não satisfaz aceite.

`npm run validate:wrangler` dentro de infra/cloudflare faz **dry-run local**.
Não há script de deploy mutável implementado; não executar Wrangler deploy real
sobre este artefato de auditoria. O account_id explícito não protege sozinho
contra colisão de Worker nem substitui inventário/manifesto.

Referências conferidas: Workers Static Assets, SPA routing, `_headers`, Wrangler
configuration e Workers best practices em developers.cloudflare.com.
