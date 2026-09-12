# Rollback — ainda não ensaiado

Não há release implantada ou versão anterior da nova aplicação. Estado: BLOCKED.
O baseline do Hablas.Chat existente não é um alvo para restauração.

Quando houver uma release:

1. Interromper próximas mudanças se aparecer regressão correlacionada.
2. Comparar IDs/marcador do manifesto com os recursos novos; origem desconhecida
   bloqueia reversão automatizada, assim como divergir de conta/zona/servidor.
3. Se schema compatível, reimplantar somente as imagens anteriores da aplicação
   pelo Coolify e a versão anterior do Worker próprio. Não atualizar dados junto.
4. Reverter só a regra/rota/registro novo comprovadamente causador, respeitando
   propriedade e impacto. Não restaurar zona inteira, proxy global ou recursos alheios.
5. Não reverter banco automaticamente. Avaliar gravações novas, compatibilidade
   e autorização de restore em plano específico; volumes não são removidos.
6. Comparar endpoints atuais autorizados, autenticação do staging, filas e dados.

Ensaio deve documentar versão anterior/nova, UUIDs, schema compatível, comandos,
duração e resultado. Rollback não garante ausência de downtime.

## O rename físico quebra três caminhos de rollback

`docs/production-rename-runbook.md` renomeia recursos cujo identificador está nos
próprios dados. Isso invalida suposições do procedimento acima:

1. **Versão de Worker.** Publicar `hablas-evo-frontend-production` cria um Worker
   novo. O histórico de versões de `hablas-evo-frontend-staging` não é acessível a
   partir dele. Antes da janela, o rollback de frontend passa a exigir republicar um
   artefato CI anterior, não promover uma versão.
2. **Imagens.** Os digests em `infra/versions.lock.yml` foram invalidados: os
   pacotes `hablas-evo-staging-*` continuam existindo, mas não são a release de
   produção. Reimplantá-los reverte também as origens compiladas no bundle, que
   apontam para `evo-api-stg.hablas.chat`. Frontend e backend devem reverter juntos.
3. **RabbitMQ.** O nó novo não lê a base Mnesia do nó antigo. Reverter para a stack
   de staging só recupera a topologia se as definitions exportadas na Fase 4 do
   runbook forem reimportadas, e nunca recupera mensagens que já estavam em trânsito.

Os volumes de staging permanecem intactos porque a Fase 5 copia em vez de mover.
Essa é a única razão pela qual as Fases 4 a 6 são reversíveis.
