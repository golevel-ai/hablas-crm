# Backup e recuperação — procedimento a concretizar

Estado: **OWNER_ATTESTED_EVIDENCE_PENDING**.

Em 12/09/2026 o responsável declarou que o ensaio de backup e restore já havia sido
realizado fora deste repositório. Nenhuma evidência foi fornecida: não há registro de
data, destino isolado, contagens conferidas nem RPO/RTO medidos, e nada foi executado
a partir deste repositório. O estado permanece **não verificado** até que esses dados
sejam preenchidos aqui; a declaração do responsável não substitui a evidência.

Isto importa agora porque `docs/production-rename-runbook.md` move dados entre volumes,
buckets e nós RabbitMQ. Sem restore comprovado, a Fase 5 do runbook opera sem rede.

Os dados do Hablas.Chat atual não fazem parte dos comandos deste projeto.

| Componente | Procedimento a implementar após versões/destinos | Evidência de restauração exigida |
|---|---|---|
| Supabase | Conferir backups/plano; dump lógico antes de migrations de risco; PITR apenas se contratado | Restore separado + contagens/integridade/roles/TLS |
| R2 | Cópia independente com credencial separada; não presumir versionamento S3 | Download autorizado, checksum, negação pública, anexos referenciados |
| Redis | Snapshot consistente via ferramenta suportada; copiar externo; AOF everysec não é backup | Jobs identificados antes/depois de restart e restore; reconciliar já executados |
| RabbitMQ | Definitions da topologia + dados em janela com broker novo parado; preservar versão/node/cookie | Retomar fila e conferir perdas/duplicatas; definitions não contém mensagens |
| ClickHouse | Backup nativo compatível com versão ou ferramenta validada, nunca cópia ativa arbitrária | Evento sintético persiste e restaura em destino separado |
| Coolify | Auditar backup do painel existente e chaves de recuperação sob controle do responsável | Plano do painel separado dos volumes da aplicação; não alterar globalmente |

Proposta de retenção a aprovar: 24 snapshots horários Redis, 7 diários e 4 semanais;
ClickHouse diário; cópias lógicas antes de migrations; definitions após mudança.
Não programar expiração/TTL/exclusão nem contratar PITR sem autorização.

## Ensaio autorizado futuro

1. Ambiente vazio separado com versões/digests e capacidade aprovados.
2. Restaurar configuração e segredos pelo cofre; verificar ownership/nomes dos volumes.
3. Restaurar dados preservando identidade RabbitMQ. Conectar apenas banco/mídia de
   recuperação, com envios externos desabilitados.
4. Validar contagens/checksums, integridade, chaves de criptografia, pendências,
   eventos e negação de acesso indevido. Reconciliar jobs antigos para evitar reenvio.
5. Registrar início/fim, perda temporal potencial, pendências e RPO/RTO medidos.

Scripts `backup.sh`/`restore.sh` não implementados: faltam destino, versões e janela
que definem comandos consistentes. Não há arquivo vazio nem comando falso de sucesso.
Sem esse ensaio, o servidor inteiro não está comprovadamente reconstruível.

## Evidência a registrar

Preencher antes da janela de rename. Enquanto houver campo vazio, o estado continua
`OWNER_ATTESTED_EVIDENCE_PENDING`.

| Campo | Valor |
|---|---|
| Data e hora do ensaio | |
| Executor | |
| Destino isolado utilizado | |
| Componentes restaurados | |
| Contagens/checksums conferidos | |
| RPO medido | |
| RTO medido | |
| Pendências encontradas | |
