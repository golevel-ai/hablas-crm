# Arquitetura de staging proposta

Frontend React/Vite → Workers Static Assets (GoLevel).
API hostname novo → Cloudflare TLS strict por hostname → proxy Coolify existente
→ gateway Evo :3030 → APIs/Sidekiq/Core/Processor/Bot/EvoFlow do commit fixado.

Supabase gerenciado: principal compartilhado + isolamento EvoFlow validado.
R2 privado exclusivo: mídia Rails e integração artifacts Processor validada.
Na VPS: Redis, RabbitMQ, ClickHouse persistentes em recurso de dados separado.

## Capacidade proposta, sujeita a teste

Dados: Redis 512 MiB (maxmemory 384 MiB), RabbitMQ 512 MiB (watermark 256 MiB),
ClickHouse 1,5 GiB (server memory 1 GiB): **2,5 GiB** de limites de container.
Aplicação: limites somam **4,5 GiB**. Total novo: **7 GiB e 4,5 CPUs de quotas**.
É proposta de staging, não capacidade comprovada: revalidar a margem antes de subir
e conferir OOM/throttling no runtime. Builds ocorrerão no CI autorizado.

Os serviços novos usam prefixos exclusivos, volumes nomeados e marcador de
propriedade do manifesto. A funcionalidade Coolify Connect to Predefined Network
implica nomes reais sufixados por UUID. Validar DNS de dentro de cada consumidor.
Compartilhar rede/host não equivale a isolamento físico.

## Adaptações pendentes antes do Compose app definitivo

- Entry points Rails sem set -x, instalação de gems ou espera infinita no runtime.
- Runtime sem bootstrap/migrations; bloquear também DDL no import do Processor.
- TLS verificado em todos os drivers, especialmente EvoFlow.
- Rota de campanhas EvoFlow no gateway com contrato/auth testados.
- Cookies exclusivos e host-only com referências de refresh consistentes; CORS
  explícito, inclusive Processor hardcoded atualmente.
- Healthcheck de processo de Sidekiq + observação de fila e heartbeat, não HTTP fictício.
- Mapear artifacts e mídia privada temporária no R2; nenhum bucket público.

Uma VPS permanece ponto único de falha. Nem alta disponibilidade, capacidade para
100 clientes nem reconstrução completa estão comprovadas.
