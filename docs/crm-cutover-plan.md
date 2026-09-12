# Plano de cutover de crm.hablas.chat

Estado: **EXECUCAO AUTORIZADA / rename fisico + GO final na mesma janela**
Owner: hablas-evo-infra
Destino: Evo CRM producao

> Atualizacao de 12/09/2026: o responsavel autorizou o rename fisico completo de
> staging para producao junto com o cutover, e a substituicao do registro A da API
> por um Cloudflare Tunnel. Os passos de migracao de dados que isso exige (bucket
> R2, Mnesia do RabbitMQ, roles Postgres e volumes Docker) estao em
> `docs/production-rename-runbook.md` e sao pre-requisito dos Gates C e D abaixo.
>
> O ensaio de backup/restore foi declarado pelo responsavel como ja realizado fora
> deste repositorio, sem evidencia registrada. O estado gravado e
> `OWNER_ATTESTED_EVIDENCE_PENDING`, nao `VERIFIED`: o bloqueio operacional abaixo
> permanece valido ate que data, destino e RPO/RTO medidos sejam registrados.

Decisões do responsável em 10/09/2026: instalação nova sem migração de dados,
API final em `api-crm.hablas.chat` e autorização total para staging e publicação
final, preservando e-mail/DKIM e a ordem dos gates deste plano.

## Situação observada

Em 10/09/2026, antes da liberação, `crm.hablas.chat` era um CNAME DNS-only com
TTL efetivo de 300 segundos para `whitelabel.ludicrous.cloud`. O host retornava
HTTP 200 e a tela de login da plataforma externa, com chamadas públicas para
`backend.leadconnectorhq.com`. Isto comprovou uso real, não um registro órfão.
No mesmo inventário, `api-crm.hablas.chat` apontava para
`brand.ludicrous.cloud` e `lp.crm.hablas.chat` para `sites.ludicrous.cloud`,
ambos DNS-only com TTL efetivo de 300 segundos. Seus IDs não foram registrados.

Após a liberação informada pelo responsável, às 15:13 UTC:

- o painel Cloudflare não lista CNAME/A/AAAA exato para `crm.hablas.chat`;
- consultas DNS públicas não retornam endereço e HTTPS não resolve;
- o Worker `hablas-evo-frontend-staging` ainda não foi criado/publicado;
- `api-crm.hablas.chat` e `lp.crm.hablas.chat` também não resolvem mais;
- `email.crm.hablas.chat` e o DKIM relacionado permanecem no DNS e não fazem parte
  deste cutover;
- nenhum DNS, Worker, domínio Coolify ou aplicação Evo foi criado nesta revisão.

Às 15:42 UTC, uma consulta read-only pela API Cloudflare confirmou zero registros
DNS e zero Workers Custom Domains para os dois hosts finais e os dois hosts `-stg`.

Às 18:47 UTC, a homologação foi publicada usando somente recursos já ativos, sem
habilitar plano ou add-on Cloudflare: `evo-stg.hablas.chat` está anexado ao Worker
`hablas-evo-frontend-staging` e `evo-api-stg.hablas.chat` aponta, com proxy ativo,
para o gateway Coolify. O responsável determinou que nenhum recurso com custo seja
ativado. O painel Cloudflare One exigia escolher um plano para criar Access; essa
ativação não foi feita. A proteção de homologação usa autenticação da aplicação,
signup desabilitado e setup já encerrado.

Na conferência read-only após a publicação, o registro exato
`email.crm.hablas.chat` não estava mais presente. Esta execução não alterou esse
hostname e não há destino confiável para recriá-lo automaticamente. MX, SPF, DMARC
e os registros DKIM do domínio raiz continuam presentes. Resolver essa divergência
com o responsável de e-mail antes do GO final.

O hostname está disponível, mas indisponível para clientes até o cutover. A
remoção feita pelo responsável não comprova que o fornecedor anterior aceitará
novamente esse domínio durante um rollback.

## Decisões obrigatórias

Antes de implantar ou publicar, registrar respostas explícitas para:

1. Confirmar se a conta/tenant do fornecedor anterior ficará preservada e se os
   três endpoints web removidos podem ser reassociados durante o rollback.
2. Definir janela, downtime aceitável, responsável de negócio, usuários
   sintéticos, canais sintéticos, SMTP e contatos de escalonamento.
3. Aprovar RPO/RTO, período de observação e critério para encerrar o fallback.

O fresh start significa que usuários, histórico, mídia e configurações anteriores
não serão importados. O aceite de negócio deve confirmar esta perda de continuidade
e comunicar criação de contas novas antes do GO.

Sem estas decisões, o cutover permanece **NO-GO**.

## Arquitetura de publicação

- Frontend final: Worker Static Assets em `crm.hablas.chat`, por Custom Domain
  exato, servido pelo Worker `hablas-evo-frontend-production`. Cloudflare não
  permite criar Custom Domain sobre CNAME existente; o conflito foi removido, mas
  deve ser revalidado imediatamente antes da escrita.
- Frontend de homologação: `evo-stg.hablas.chat`, sem rotas wildcard. Por decisão
  do responsável, Cloudflare Access não foi ativado; a autenticação da aplicação é
  a barreira de acesso disponível no plano atual.
- API de homologação: `evo-api-stg.hablas.chat`, terminando TLS no proxy Coolify e
  encaminhando somente ao gateway da stack.
- API final: `api-crm.hablas.chat`, publicada por **Cloudflare Tunnel** em vez de um
  registro A para o IP da origem. O `cloudflared` roda em dois conectores na VPS e
  encaminha somente para `http://hablas-evo-production-gateway:80` pela rede Docker.
  Isso remove o acesso direto ao IP por Host header apontado no bloqueio 4 do Gate B
  e permite fechar as portas 80/443 na origem após a janela de observação. A
  latência não melhora: o túnel adiciona um hop e o ganho é de superfície de ataque.
- Banco/filas/storage: recursos dedicados já preparados, sem reutilizar o CRM
  anterior.
- O browser usa origens base sem `/api/v1`; o gateway atende API, `/cable`, OAuth,
  webhooks, ActiveStorage, Processor e campanhas EvoFlow.

O build de homologação e o build final devem ser artefatos identificáveis. As
origens Vite são compiladas no bundle; trocar DNS não altera o bundle existente.

## Bloqueios técnicos anteriores à implantação

1. **Correção local pronta; runtime pendente:** Auth mantém `FORCE_SSL=true`,
   `assume_ssl`, HSTS e validação HTTPS do Doorkeeper. O comportamento do HTTP
   interno deve ser comprovado no container antes da publicação.
2. **Correção local pronta; runtime pendente:** Auth prioriza o ambiente para o
   serviço e todos os campos R2; valores persistidos não podem selecionar disco,
   bucket ou credenciais diferentes.
3. **Correção local pronta; navegador pendente:** o Worker aplica nosniff/CSP,
   preserva embedding de `/widget` e rejeita caminhos backend antes do fallback SPA.
   `connect-src https: wss:` e `frame-src https:` preservam integrações configuráveis;
   restringi-los exige proxy/allowlist de produto, não uma lista incompleta.
4. **Contrato local pronto; digest pendente:** o contexto do gateway comprova CORS
   e `/api/v1/campaigns`; a imagem final ainda precisa de CI e verificação do digest.
5. Login social Devise permanece fora do lançamento. Não expor `/auth/*` até
   implementar state/CSRF, bloquear signup indevido e aplicar rate limit.
6. **Bloqueado operacionalmente:** o responsável declarou em 12/09/2026 que backup e
   restore foram ensaiados fora deste repositório, sem fornecer evidência. Smoke R2
   de objeto não é evidência de recuperação da aplicação. Registrar data, destino
   isolado e RPO/RTO medidos em `docs/backup-restore.md` antes da janela; até lá o
   rename físico da Fase 5 do runbook opera sem recuperação comprovada.
7. **Novo com o rename físico:** bucket R2, base Mnesia do RabbitMQ, roles Postgres
   e volumes Docker gravam o identificador antigo nos próprios dados e não aceitam
   rename no lugar. Ver `docs/production-rename-runbook.md`.

Cada correção exige teste de contrato e uma nova release imutável antes de criar
recursos públicos.

## Fases e gates

### Gate A: prontidão técnica

1. Corrigir os bloqueios acima e passar CI completo.
2. Fixar todos os digests e registrar o hash do bundle frontend.
3. Confirmar capacidade atual do servidor e orçamento por container.
4. Definir API final, origens, CORS, callbacks OAuth e URLs de webhook.
5. Implementar backup e restaurar em destino isolado, medindo RPO/RTO.

Saída: release candidata reproduzível, sem qualquer hostname público de cliente.

### Gate B: homologação isolada

1. Reexecutar inventário autenticado Cloudflare e Coolify.
2. Criar a aplicação somente no projeto/ambiente/servidor registrados, inicialmente
   sem domínio ou porta pública.
3. Criar o primeiro administrador por uma chamada server-local na rede Docker ao
   Auth, marcando `X-Forwarded-Proto: https`, com o segredo entregue por entrada
   protegida e sem logs. Confirmar que uma segunda chamada é recusada e que os grants
   de `super_admin` estão íntegros.
4. Somente após fechar o bootstrap, publicar API e frontend nos dois hosts `-stg`.
   Access permanece não ativado por restrição de custo; manter autenticação da
   aplicação, signup desabilitado e setup fechado. A API não deve ser anunciada
   como privada enquanto o IP de origem continuar acessível por Host header.
5. Executar toda a matriz de aceite abaixo com dados e destinos sintéticos.
6. Ensaiar rollback de imagem, Worker, banco restaurado e filas.

Saída: aceite técnico e de negócio assinado. Falha mantém `crm.hablas.chat` sem
vínculo com o Worker.

### Gate C: fresh start e preparação final

0. Executar as Fases 1 a 6 de `docs/production-rename-runbook.md`: imagens de
   produção verificadas, bucket R2 copiado, roles Postgres criadas, filas drenadas,
   volumes movidos e a stack `hablas-evo-app-production` saudável. O preflight
   remoto recusa enquanto `infra/versions.lock.yml` apontar para pacotes pré-rename.
1. Preservar um export do CRM anterior apenas como evidência/fallback, se disponível;
   não importar dados no Evo conforme a decisão de fresh start.
2. Criar e validar contas novas, dados sintéticos e configuração inicial. Comunicar
   que sessões, senhas, histórico, mídia e configurações anteriores não continuam.
3. Criar o tunnel `hablas-evo-production`, subir os dois conectores e criar a rota
   DNS de `api-crm.hablas.chat` para o tunnel. Executar os testes da API pelo
   hostname final — incluindo `wss://.../cable` e o streaming SSE do processor, que
   são os que mais expõem erro de configuração de túnel — antes de publicar
   `crm.hablas.chat`.
4. Atualizar callbacks OAuth e webhooks para a API nova apenas na janela aprovada.
5. Gerar bundle final apontando para as origens finais e verificar ausência de
   placeholders, `.invalid`, localhost e segredos.
6. Configurar a aplicação com `FRONTEND_ORIGIN=https://crm.hablas.chat`, reiniciar
   os serviços afetados e validar pela origem antes de publicar o frontend.
7. Capturar imediatamente antes da escrita: DNS completo dos hosts, Custom Domains,
   routes, Worker/version ID, aplicação Coolify, digests, saúde e backups.

Saída: autorização explícita **GO**, com executor, observadores e horário.

### Gate D: cutover

1. Confirmar novamente que não existe CNAME/A/AAAA/Worker/Pages/Tunnel/LB/Access
   conflitante em `crm.hablas.chat`.
2. Confirmar API, aplicação, filas, banco e storage saudáveis.
3. Anexar `crm.hablas.chat` como Custom Domain exato do Worker final. Não criar
   wildcard, rota de zona nem alterar SSL global.
4. Aguardar certificado ativo e validar DNS em resolvedores independentes.
5. Executar smoke anônimo e autenticado antes de anunciar disponibilidade.
6. Monitorar continuamente pelo período aprovado; não remover o fallback antigo.
7. Manter as portas 80/443 da origem abertas durante a observação. Fechá-las e
   marcar `cloudflare.tunnel.origin_ports_closed` só na Fase 8 do runbook: enquanto
   abertas, o caminho de rollback direto continua disponível.

## Matriz mínima de aceite

- Todos os nove processos da aplicação healthy e comunicação interna sem redirect
  HTTPS indevido.
- Setup único, login, refresh após expiração, logout, reset de senha e MFA quando
  habilitado; cookies Secure, HttpOnly, host-only e com nomes Evo.
- CRUD de usuários, contatos, conversas, mensagens, pipelines, templates e
  automações; RBAC de administrador e agente.
- `wss://<api>/cable` conecta, recebe evento e reconecta; WebSocket do Processor
  autoriza e conclui uma interação.
- Upload/download de anexo CRM e avatar Auth continuam após restart e redeploy; os
  objetos aparecem no bucket privado R2, nunca em disco efêmero.
- CORS aceita somente frontend/API aprovados, preflight funciona e origem não
  aprovada recebe 403.
- Campanhas, jornadas, segmentos, formulários públicos, chat público, webhooks,
  OAuth e ActiveStorage chegam ao serviço correto pelo gateway.
- Cada tipo de canal previsto passa envio e recebimento sintéticos; nenhum contato
  ou canal real é acionado durante homologação.
- Restore isolado preserva contagens, vínculos, mídia, chaves criptográficas e
  permissões; filas não duplicam envios.
- Navegação direta, refresh de rota SPA, headers/CSP, ausência de resposta HTML em
  `/api/*` e ausência de credenciais/placeholders no bundle.

## Monitoramento e rollback

### Aceite executado em staging em 10/09/2026

Passaram: TLS e health públicos, CORS permitido e negação 403 para origem não
aprovada, login, validate, refresh, APIs autenticadas do dashboard, navegação SPA,
setup ativo redirecionado para a aplicação, logout e handshake ActionCable 101 com
welcome/ping. O host frontend devolveu JSON 404 para caminho de backend, sem fallback
HTML. O bundle CI teve 63 hashes e hash de árvore verificados antes do deploy.

Permanece pendente o restante da matriz: reset de senha/SMTP, MFA quando habilitado,
CRUD completo e RBAC de agente, Processor WebSocket, mídia após restart/redeploy,
canais e integrações sintéticas, restore isolado, rollback e carga. O beacon de
analytics já presente na zona é bloqueado pela CSP; isso gera aviso no console, sem
impacto observado na aplicação. Staging parcial não constitui o GO final.

Disparar rollback com qualquer perda/inconsistência de dados ou mídia, escrita no
ambiente errado, falha de autenticação generalizada, quebra de canal crítico ou
backlog sem processamento. Limiares iniciais a aprovar:

- duas falhas consecutivas no sintético login/refresh;
- incapacidade confirmada de enviar ou receber mensagens por cinco minutos;
- taxa de 5xx acima de 2% por cinco minutos;
- Sidekiq/RabbitMQ sem processamento bem-sucedido por dez minutos;
- indisponibilidade persistente de ActionCable ou Processor WebSocket.

Rollback de versão Evo:

1. Congelar novas mudanças e capturar evidência.
2. Reimplantar os digests anteriores compatíveis no Coolify.
3. Para erro somente no frontend, promover a versão Worker anterior. Rollback de
   Worker afeta imediatamente todos os seus domínios/rotas e não substitui rollback
   de DNS para o fornecedor anterior.

Rollback de tráfego para o CRM anterior, somente se o Gate C comprovou o fallback:

1. Parar ou colocar o Evo em read-only, drenar/controlar filas e fazer snapshot dos
   dados escritos após o GO.
2. Remover o Custom Domain `crm.hablas.chat` e aguardar a remoção do DNS gerenciado.
3. Recriar CNAME DNS-only `crm` para `whitelabel.ludicrous.cloud` com TTL de
   300 segundos (exibido como Auto),
   conferindo que o fornecedor ainda aceita o domínio e retorna o tenant correto.
4. Se necessários ao fallback validado, recriar também `api-crm` para
   `brand.ludicrous.cloud` e `lp.crm` para `sites.ludicrous.cloud`, ambos DNS-only
   com TTL de 300 segundos (exibido como Auto). Como seus IDs não foram capturados,
   esta etapa é manual e bloqueada até o fornecedor confirmar os destinos. Nunca
   alterar o CNAME de e-mail ou DKIM nesse procedimento.
5. Reverter callbacks/webhooks alterados na janela.
6. Reconciliar toda escrita recebida pelo Evo antes de reabrir o CRM anterior.

Sem freeze ou reconciliação, voltar o DNS cria split-brain e não é rollback seguro.
Nunca reverter schema ou restaurar banco automaticamente durante esse procedimento.

## Aprovações separadas

- **Aprovação 1:** criar recursos de homologação `evo-stg`/`evo-api-stg`. *(concedida)*
- **Aprovação 2:** criar `api-crm`, provisionar o fresh start e alterar callbacks externos.
- **Aprovação 3:** anexar `crm.hablas.chat` ao Worker final.
- **Aprovação 4:** retirar o fallback após o período de observação.
- **Aprovação 5:** executar o rename físico (R2, RabbitMQ, roles Postgres, volumes),
  que envolve indisponibilidade e movimentação de dados sem rename reversível.
- **Aprovação 6:** fechar as portas 80/443 da origem após a observação do tunnel.

A liberação do registro DNS pelo responsável não substitui estas quatro aprovações.

## Referências

- `infra/environment.target.yml`
- `infra/coolify/compose.app.yml`
- `infra/cloudflare/wrangler.jsonc`
- `docs/domain-allocation.md`
- `docs/deploy-cloudflare.md`
- `docs/backup-restore.md`
- `docs/rollback.md`
- Cloudflare Workers Custom Domains:
  https://developers.cloudflare.com/workers/configuration/routing/custom-domains/
- Cloudflare Workers Rollbacks:
  https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/
