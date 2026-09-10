# Entradas e bloqueios

Atualizado em 10/09/2026 (America/Sao_Paulo). Segredos devem ser disponibilizados
no cofre/Coolify/CI; não colar em relatórios nem versionar DSNs.

| Grupo | Estado observado | Bloqueio / retomada |
|---|---|---|
| Código | VERIFIED: fork indicado pelo responsável, `main` fixada em `fa6924df23b863de30b065d25e301bb414593bd5`; 11 gitlinks recursivos inicializados | Conferir lock antes do build; não atualizar submódulos por branch |
| Servidor | VERIFIED: UUID, IP no host, SO, Docker, Compose e capacidade pontual | Aprovar orçamento por container e revalidar capacidade antes de criar |
| Coolify | 4.3.18; projeto/ambiente registrados; stack de dados implantada e healthy; aplicação ausente | Revalidar capacidade/domínios e criar aplicação somente após autorização remota |
| Cloudflare | Conta/zona confirmadas; zero DNS e Custom Domains nos quatro hosts às 17:37 UTC | Revalidar imediatamente antes da escrita; preservar e-mail/DKIM |
| Supabase | **VALIDATED**: projeto dedicado `znxlfqctnezrropcbftw`, TLS, schemas e roles runtime comprovados | Não reutilizar o projeto anterior; restore drill ainda pendente |
| R2 | Dois buckets privados, credenciais restritas e smoke cruzado validados | Backup/restore real e monitoramento ainda pendentes |
| Registry | Release `38e99df` pública no GHCR e digests verificados | Receita Gate A mudou; executar CI autorizado e importar novos digests |
| E-mail | PENDING_OWNER_INPUT | SMTP/remetente de staging antes de recuperação/notificações |
| Integrações | PENDING_OWNER_INPUT | Credenciais e destinatários sintéticos autorizados; sem canais reais |
| Backups | PENDING_OWNER_INPUT | Destino independente, credenciais, retenção e ambiente de recuperação autorizados |
| Publicação | `FULL_STAGING_AND_FINAL_DEPLOYMENT_AUTHORIZED`; fresh start, frontend `crm` e API `api-crm` escolhidos | Executar staging, validar e só então publicar os hosts finais |
| Toolchain local | Node 26 padrão; Node 20.20/22.19 executados via npx; Python 3; Docker ausente | Frontend passou em Node 20; Wrangler passou em Node 22; containers dependem do CI futuro |

## Correções técnicas locais do Gate A

Compatibilidade confirmada na documentação oficial: Supabase está listado em
https://docs.evolutionfoundation.com.br/self-hosted, Passo 3, Opção C, como provedor
PostgreSQL/pgVector compatível. A arquitetura aprovada com Supabase está mantida;
as correções abaixo tratam da configuração e validação da implantação específica.

1. Auth/CRM recebem `PGSSLMODE=verify-full` e CA no contexto gerado.
2. EvoFlow usa opções TLS com CA e verificação completa; testes locais e banco real passaram.
3. Gateway recebe rota restrita de campanhas para EvoFlow e CORS por origem exata.
4. Bootstrap principal nativo foi validado sem mascarar históricos de migration.
5. Imagens base estão fixadas por digest; a nova receita ainda precisa de CI autorizado.

As sessões web habilitam inventário manual autenticado. Não extrair tokens/cookies
dessas sessões para arquivos de shell nem aproveitar segredos de aplicações existentes.

## Supabase

O projeto anterior `fizdiennudpyqrzmdukm` permanece preservado e não é destino desta
implantação. O destino dedicado validado é `znxlfqctnezrropcbftw`; detalhes e provas
sanitizadas estão em `supabase-validation.md`. Segredos ficam somente no cofre/local.

## Atualização do responsável — frontend dos clientes

Frontend final: **crm.hablas.chat**. API final: **api-crm.hablas.chat**. Ambos foram
liberados pelo responsável e estavam sem DNS/Custom Domain na leitura registrada,
e agora podem ser alocados na sequência staging/final autorizada; ver
`domain-allocation.md` e `crm-cutover-plan.md`.
