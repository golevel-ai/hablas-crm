# Entradas e bloqueios

Atualizado em 09/09/2026 (America/Sao_Paulo). Segredos devem ser disponibilizados
no cofre/Coolify/CI; não colar em relatórios nem versionar DSNs.

| Grupo | Estado observado | Bloqueio / retomada |
|---|---|---|
| Código | VERIFIED: fork indicado pelo responsável, `main` fixada em `fa6924df23b863de30b065d25e301bb414593bd5`; 11 gitlinks recursivos inicializados | Conferir lock antes do build; não atualizar submódulos por branch |
| Servidor | VERIFIED: UUID, IP no host, SO, Docker, Compose e capacidade pontual | Aprovar orçamento por container e revalidar capacidade antes de criar |
| Coolify | Sessão web autenticada; 4.3.18; projeto e staging vazios criados com UUIDs registrados | Inventário completo de domínios/proxy e fluxo Compose; MCP Coolify não disponível nesta sessão |
| Cloudflare | Sessão web autenticada; conta/zona confirmadas | Finalizar alocação, TLS e proteção do staging. Token de automação não disponível no ambiente do shell |
| Supabase | **PENDING_OWNER_INPUT** | Aguardar conexões prometidas; validar principal e isolamento EvoFlow, TLS, permissões, orçamento e bootstrap |
| R2 | Inventário autenticado; nenhum bucket novo | Aprovar custo se aplicável, criar bucket exclusivo privado e credencial restrita |
| Registry | GitHub autenticado; destino de imagens ainda não definido | Definir registry autorizado; build linux/amd64 e digests das imagens próprias |
| E-mail | PENDING_OWNER_INPUT | SMTP/remetente de staging antes de recuperação/notificações |
| Integrações | PENDING_OWNER_INPUT | Credenciais e destinatários sintéticos autorizados; sem canais reais |
| Backups | PENDING_OWNER_INPUT | Destino independente, credenciais, retenção e ambiente de recuperação autorizados |
| Publicação | Staging autorizado no PRD; promoção de produção não autorizada | Bloqueada até preflight completo; frontend antecipado exige Access restrito |
| Toolchain local | Node 26.7.0/npm 11.19.0; Python 3; Docker ausente | Build local frontend possível; validar release com toolchain Node 20 do Dockerfile fixada e build backend em CI autorizado |

## Bloqueios técnicos descobertos no commit

Compatibilidade confirmada na documentação oficial: Supabase está listado em
https://docs.evolutionfoundation.com.br/self-hosted, Passo 3, Opção C, como provedor
PostgreSQL/pgVector compatível. A arquitetura aprovada com Supabase está mantida;
as pendências abaixo tratam da configuração e validação da implantação específica.

1. `POSTGRES_SSLMODE` não é consumida por `config/database.yml` de Auth/CRM.
   Validar libpq `PGSSLMODE=verify-full` + CA no runtime ou adaptação explícita.
2. EvoFlow: `ormconfig.ts` desativa validação de certificado em `require`; os demais
   valores desativam SSL. Corrigir configuração de TLS no fork e testar antes de conectar.
3. Gateway não possui rota de campanhas para EvoFlow; frontend exige
   `VITE_EVOFLOW_API_URL`. Necessária adaptação restrita do gateway e teste de contrato.
4. Bootstrap compartilhado carrega schema CRM e marca migrations Auth. Exige
   comparação estrutural; não executar o Makefile de desenvolvimento no Supabase.
5. Imagens/algumas ferramentas de build upstream usam tags mutáveis. Fixar imagens
   próprias e dependências de build; frontend local não comprova release reproduzível.

As sessões web habilitam inventário manual autenticado. Não extrair tokens/cookies
dessas sessões para arquivos de shell nem aproveitar segredos de aplicações existentes.

## Atualização do responsável — MCP Supabase

Fornecido project ref `fizdiennudpyqrzmdukm` por configuração MCP, com
`read_only=true`. Configuração salva em `opencode.json`. Isso não fornece DSNs,
roles, CA, senha nem confirma se o projeto corresponde ao banco principal ou EvoFlow.
Conexões continuam PENDING_OWNER_INPUT e identidade do projeto UNVERIFIED até
consulta autenticada. Reiniciar OpenCode para carregar o novo MCP e autenticar com
`opencode mcp auth supabase`. Não habilitar escrita ou branching mutável.

Resultado: comando literal não encontrado no PATH; alternativa
`npx --yes opencode-ai@1.18.30 mcp auth supabase` executada. Primeiro fluxo expirou;
segundo confirmou **Authentication successful!**. O CLI aceitou a configuração.
O download do schema público pelo cliente Python retornou HTTP 403; não declarar
validação externa de JSON Schema. A sessão atual ainda exige reinício para carregar
as ferramentas MCP; OAuth concluído não comprova identidade/schema do projeto.

O responsável também forneceu URL, chave publicável, chave secreta Data API e JWKS.
Os valores das chaves não foram gravados no Git, manifesto ou configuração frontend.
Esses dados não são conexões PostgreSQL. Foi recomendada a revogação da chave
secreta compartilhada no chat; execução da revogação permanece com o responsável.

## Atualização do responsável — frontend dos clientes

Hostname desejado: **crm.hablas.chat**. Demais subdomínios a cargo do executor,
com verificação de disponibilidade. O CNAME existente exige revisão do uso/destino
e plano de transição na etapa de domínios; ver domain-allocation.md.
