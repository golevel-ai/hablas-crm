# Build e publicação das imagens

Branch autorizada: `infra/staging-deployment`.
Commit de infraestrutura da release construída: `b24252762e78188304a1c3b4baef1dfd94b1ee92`.
Código da aplicação: commit/base e gitlinks preservados em versions.lock.yml.

CI: https://github.com/golevel-ai/hablas-crm/actions/runs/34434439582

O run terminou **success**: etapa verify e os sete builds gateway/Auth/CRM/Core/
Processor/Bot/EvoFlow. Os testes de guardas, TLS e PostgreSQL descartável do EvoFlow
passaram também no runner Linux. Nenhum build foi executado na VPS compartilhada.

## Publicação

O GHCR criou os pacotes inicialmente privados porque a organização proibia Public.
O responsável autorizou explicitamente habilitar a política Public de criação de
packages na organização golevel-ai. O ajuste foi aplicado pela interface oficial;
as demais opções permaneceram como observadas.

Somente os sete packages desta implantação foram tornados públicos. Antes da
mudança de cada pacote, foram conferidos repositório, tag do commit e histórico
compatível com este run (uma versão tagged e duas untagged da imagem/atestado).

`scripts/ops/import_release.py` verificou posteriormente, **sem credenciais GitHub**:

- acesso anônimo aos sete manifests no GHCR;
- SHA-256 do conteúdo de cada manifest igual ao digest devolvido pelo CI;
- presença de uma plataforma linux/amd64;
- correspondência entre código-fonte, receita, commit de infraestrutura e receipts.

Os digests completos estão em `infra/versions.lock.yml` e no manifesto operacional
local. Pull de imagem não depende do PAT pessoal do responsável.

## Reexecuções

O workflow está sendo ajustado para reutilizar uma release verificada quando só
documentação/controle operacional mudar, evitando um ciclo commit-digests → novo
build → novos digests. Imagens novas continuam necessárias quando o código ou a
receita mudar. Uma tag de release já existente não deve ser sobrescrita.

Publicação de imagem não implica deployment nem validação funcional. O bootstrap
principal Rails ainda precisa do ensaio de compatibilidade; os recursos app/data
do Coolify ainda não foram criados neste checkpoint.
