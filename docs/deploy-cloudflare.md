# Runbook frontend Workers — publicação bloqueada

Conta GoLevel confirmada; IDs no target e Wrangler. Configuração exclusiva de
staging, sem rota, workers.dev ou preview URL públicos. Nenhum Worker criado.
Wrangler fixado em 4.130.0 no package.json operacional, independente do frontend.

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
não foi usado). `npm ci --no-audit --no-fund` preservou o lockfile. Build TypeScript +
Vite concluiu com Node 26.7.0/npm 11.19.0, URLs públicas `https://api.build.invalid`.
É teste de compilação, não artefato de release. Repetir com Node 20 fixado/compatível
ao Dockerfile e URLs finais após resolver a rota de campanhas.

O cliente acrescenta `/api/v1`; ActionCable converte a origem e acrescenta `/cable`.
Não repetir sufixos. VITE_EVOFLOW_API_URL continua necessária para campaignsService;
sem adaptação do gateway ela não pode ser substituída silenciosamente pela URL CRM.

## Antes da publicação

1. Resolver os bloqueios de domain-allocation.md e definir Access restrito do
   frontend antecipado. Não liberar API/setup incompleto nem canais de produção.
2. Gerar `_headers` no dist preservando nosniff e a CSP do Nginx, ajustando connect
   às origens verificadas; preservar exceção de embedding `/widget` com política
   apropriada. Este passo ainda não foi implementado/testado, não declarar paridade.
3. Tratar explicitamente rotas `/api/*` no host frontend para não mascarar JSON
   com SPA. O template assets-only atual ainda usa fallback SPA genérico.
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
