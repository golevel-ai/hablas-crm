# Dados de staging implantados no Coolify

10/09/2026. Recurso **hablas-evo-data-staging**, UUID
`nrvbltvkzmzvivrbkldjok6y`, projeto jjxcrsedavkskvcbnuvmkaql / staging
xukzvsnkjemq085zitdzzytf, servidor hwt9rmdg9rrodfb9hilh8vcn / 51.81.80.55.

## Estado verificado

| Serviço | DNS do container | Limite efetivo | Estado |
|---|---|---|---|
| Redis | hablas-evo-staging-redis-nrvbltvkzmzvivrbkldjok6y | 512 MiB / 0,25 CPU | healthy |
| RabbitMQ | hablas-evo-staging-rabbitmq-nrvbltvkzmzvivrbkldjok6y | 512 MiB / 0,25 CPU | healthy |
| ClickHouse | hablas-evo-staging-clickhouse-nrvbltvkzmzvivrbkldjok6y | 1536 MiB / 0,5 CPU | healthy |

Docker inspect confirmou **PortBindings vazio nos três containers** e o marcador
de propriedade correto. A tela Domains confirmou nenhum domínio configurado.
Foram usadas imagens linux/amd64 fixadas por digest em versions.lock.yml.

## Volumes reais e rede

O parser do Coolify usou nomes prefixados pelo UUID, em vez dos `name` sugeridos
no Compose original. Os volumes efetivamente criados e preservados no reinício são:

- nrvbltvkzmzvivrbkldjok6y_redis-data
- nrvbltvkzmzvivrbkldjok6y_rabbitmq-data
- nrvbltvkzmzvivrbkldjok6y_clickhouse-data

Não renomear esses volumes. Conferir os Mounts e o UUID antes de reexecuções.
Redes: a rede própria nrvbltvkzmzvivrbkldjok6y e a rede predefinida `coolify`.
O RabbitMQ manteve hostname hablas-evo-staging-rabbitmq e node identity estável.
A rede predefinida é compartilhada e não equivale a isolamento físico.

## Particularidades do Coolify 4.3.18 tratadas

1. O editor de código acrescentou indentação ao preenchimento multilinha. A primeira
   tentativa foi rejeitada no parse, antes de criar recurso. O conteúdo exato foi
   enviado pela propriedade pública do editor Livewire, mantendo validação/autorizações
   nativas do backend. A criação válida ocorreu uma única vez.
2. Configs relativos foram materializados como `configs.content` para o editor inline.
   Fonte e renderer estão versionados; somente o resultado público é enviado ao Compose.
3. O parser injeta `.env` em todos os containers. Isso foi observado em Docker inspect
   e confirmado no código do tag v4.3.18. Strings vazias também podem ser substituídas
   pelo valor do banco do Coolify.
4. O renderer passou a sobrescrever variáveis não utilizadas com o valor não secreto
   `unused-in-this-container`. Referências usadas pelo próprio serviço são preservadas.
   Após reinício **somente da stack nova**, os serviços ficaram healthy novamente,
   os volumes permaneceram os mesmos e os segredos de outros serviços ficaram mascarados.
   O alias RABBITMQ_PASSWORD permanece disponível no próprio RabbitMQ por ser usado
   para resolver RABBITMQ_DEFAULT_PASS; não permanece disponível no Redis/ClickHouse.

Credenciais reais foram geradas uma vez, salvas em arquivo local 0600 vinculado ao
owner/UUID e transportadas à tela de env sem valores em chat ou scripts versionados.
Uma leitura posterior confirmou igualdade dos oito valores persistidos com o arquivo
protegido. O renderer guarda somente referências públicas no YAML.

## Preservação e limites

Após o primeiro start: memória disponível 9.155 MiB; workloads anteriores de n8n,
pgAdmin, PostgreSQL, Redis, WireGuard e proxy permaneceram saudáveis, com uptime
de dois meses. Sentinel apresentou reinícios/estado starting também nas observações
de baseline; nenhuma ação explícita de restart do Sentinel foi executada.

Esta etapa comprova implantação/saúde/limites/volumes, não backup ou restauração.
Ainda faltam: consumo pela aplicação, teste de jobs, pausa real de 60 minutos no
broker, evento ClickHouse e restauração externa. Nenhum desses testes foi marcado PASS.

## Rotação preventiva posterior

Valores operacionais apareceram em outputs de inspeção e foram tratados
como comprometidos antes da promoção. Após a última exposição, foram rotacionados novamente o migrator principal, todas
as chaves de aplicação ainda não usadas e REDIS_PASSWORD, RABBITMQ_PASSWORD,
RABBITMQ_ERLANG_COOKIE e CLICKHOUSE_PASSWORD. RabbitMQ/ClickHouse foram atualizados
live; o cookie persistido foi substituído atomicamente; somente esta stack foi
reiniciada. Depois, os três serviços voltaram a healthy e o host comprovou login com
as credenciais novas, cookie novo, portas privadas e todas as 69 máscaras EVO_OPS.
O redeploy materializou os 31 valores atuais no `.env`; a verificação removeu o
payload temporário de rotação. A chave de criptografia foi validada como uma chave
Fernet de 32 bytes, Base64 URL com padding. Nenhum volume, fila ou tabela foi removido.
