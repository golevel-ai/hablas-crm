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
