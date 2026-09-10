# Baseline do ambiente existente

Observação: 09/09/2026, aproximadamente 22:19–22:32 America/Sao_Paulo
(10/09/2026 01:19–01:32 UTC). **Somente leitura; implantação nova ainda ausente.**

## Identidades confirmadas

| Item | Evidência autenticada |
|---|---|
| Coolify | `https://my.golevel.ai/`, versão `4.3.18`, equipe exibida `Go Team` |
| Servidor | `VPS-US-VA-002-OP`, UUID `hwt9rmdg9rrodfb9hilh8vcn` |
| IP | Cadastro e interface `ens3` no host: `51.81.80.55` |
| SO / arquitetura | Ubuntu 24.04.4 LTS; kernel 6.8.0-124-generic; x86_64 |
| Runtime | Docker 29.5.2; Compose 5.1.4; NTP sincronizado |
| Cloudflare | GoLevel, account `85354ee4fc8d1c079a66f6321a5c78c5` |
| Zona ativa | hablas.chat, zone `b0a4153d93f81cd7957e34cdfcd11e60` |

A lista geral de servidores exibiu `Attention required`, mas os detalhes do destino
exibiram `Ready`; o terminal autenticado confirmou conectividade. Não foi usado o
botão de revalidação nem alterada configuração do servidor. O usuário SSH não tem
acesso direto ao socket Docker; consultas de leitura funcionaram com `sudo -n`.

## Capacidade: amostra, não teste de carga

- 6 CPUs; memória total 11.676 MiB, usada 2.061 MiB, disponível 9.615 MiB.
- Sem swap. Disco raiz 96 GB, usados 15 GB, disponíveis 82 GB (15% usado).
- Reservar pelo menos aproximadamente 2,3 GiB para SO/Coolify/picos, além das
  necessidades dos workloads existentes; repetir a medição antes de provisionar.
- Não há evidência de 16 vCPU, 32 GB RAM ou 400 GB NVMe neste destino.

## Workloads existentes protegidos

O painel listou cinco recursos gerenciados, todos `Running:healthy`:
`n8n`, `pgadmin`, PostgreSQL, Redis e `wireguard-us`. A aba Unmanaged não listou
containers. O Docker listou 11 containers: proxy, Sentinel, cinco de n8n,
WireGuard, pgAdmin, PostgreSQL independente e Redis independente. Todos saudáveis
na amostra; o Sentinel tinha uptime de minutos e os demais de dois meses.
Nenhuma ação de restart foi executada por esta implantação.

Os sete volumes existentes e as redes dos recursos foram inventariados em terminal;
nenhum tinha prefixo `hablas-evo`. A rede compartilhada `coolify` já existe.
Os nomes detalhados de terceiros ficam na evidência operacional local, excluída
do Git. Coincidência futura de nome não autoriza reutilização.

Portas publicadas observadas: proxy 80/443/8080 TCP e 443 UDP; WireGuard 51820 UDP.
PostgreSQL/Redis não tinham bindings de host. Isto **não substitui** teste externo
de firewall/proteção de 8080. Alterar o proxy/firewall existente está fora desta execução.

## Cloudflare

- DNS: 47 registros, consulta completa de uma página. Nenhum wildcard DNS listado.
- **`evo.hablas.chat` já existe**, registro A `047cfa7c83df09e29993dd2791b6841b`.
  Não está disponível para este projeto.
- Nenhum registro exato dos dois candidatos de staging na amostra.
- 13 Workers existentes; nenhum `hablas-evo-frontend-staging`.
- 12 Workers custom domains; nenhum candidato de staging.
- Duas rotas Workers existentes: `hablas.chat/*` e `www.hablas.chat/*`, ambas
  associadas a `hablas-site-v2`. Preservar integralmente.
- Pages: zero projetos na consulta válida (`per_page=10`). A tentativa com 100
  retornou 400; foi corrigida, não interpretada como lista vazia.
- Um Tunnel ativo, gerenciado remotamente: dois ingress hostnames em `golevel.ai`
  e regra final sem hostname. Nenhum hostname `hablas.chat` observado.
- Zero Load Balancers e zero Page Rules na zona.
- Rulesets de zona: três managed, um custom WAF, um redirect. As duas regras
  customizadas ativas restringem-se, respectivamente, a `n8n.hablas.chat` e
  `apps.hablas.chat`; não abrangem os candidatos. Conta: um ruleset managed listado.
- Duas aplicações Access: painel Coolify e outro Worker; nenhuma para staging novo.
- SSL global observado: **Full**, não Full (strict). Validar regra isolada para
  o novo hostname antes de publicar; não mudar a política global.
- Quatro buckets R2 existentes; nenhum pertence a este projeto. Não reutilizar.

## Limites desta baseline

Inventário ainda não libera publicação: faltam revisar todos os domínios de recursos
Coolify em outros hosts/equipes acessíveis, eventuais configurações dinâmicas do proxy,
cookies do sistema atual e efeitos das políticas gerenciadas. A disponibilidade HTTP
dos endpoints existentes e seu comportamento de sessão ainda não foram comparados.
Respostas completas de APIs, cookies, tokens e dados de clientes não integram este documento.

Revalidar identidade, inventário, capacidade e comportamento antes e depois de cada
escrita. A amostra é histórica; não constitui autorização permanente de nomes.

## Comparação após metadados novos

09/09/2026 aproximadamente 23:00–23:05 America/Sao_Paulo:

- Projeto novo e staging vazio registrados em change-plan.md; nenhum workload novo.
- Os quatro projetos anteriores permanecem; agora cinco no total. Mesmos cinco
  recursos gerenciados no servidor, todos `Running:healthy` após a alteração.
- GET de `hablas.chat/` e `app.hablas.chat/`: 200 antes/depois. Sem Set-Cookie nas
  respostas públicas consultadas; isto não audita cookies dos fluxos autenticados.
- Primeiro GET de `www.hablas.chat/` não concluiu no cliente de teste; nova leitura
  respondeu 301. Não existe baseline HTTP prévia conclusiva para comparar esse host.
- DNS reconsultado às 02:04:56Z: 47 registros, sem mudança nos campos
  id/name/type/content/proxied/ttl/priority, ordenados por ID e serializados em JSON.
  SHA-256 antes/depois: `8cc9908de0db3b87cd629392e3a066f9579a410dbdc7374849e816a3915dbdc0`.

Verificação de preservação é parcial: nenhuma configuração anterior foi editada
por esta execução, mas cookies autenticados, firewall externo e todos os endpoints
de integrações ainda não foram verificados.
