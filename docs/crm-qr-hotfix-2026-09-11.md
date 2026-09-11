# CRM QR response hotfix — 2026-09-11

- Source correction: `443f16c1c2c96e71ec83b58286ce39a1a8fd00a4`.
- Build: https://github.com/golevel-ai/hablas-crm/actions/runs/34565393820
- CRM image: `ghcr.io/golevel-ai/hablas-evo-staging-crm@sha256:e340fdb305db629ec88ad6eaacd9677109b973c13dc395feeca5c16724d9264c`.
- Previous CRM image: `ghcr.io/golevel-ai/hablas-evo-staging-crm@sha256:9be2b0a2a09f605cd994b20941d996f828741fa155097787fc0647689ee9f1fe`.
- Coolify resource: `j5tqzqszm8di0pxs8vswon24` (`hablas-evo-app-staging`).

The build overlay now accepts lowercase `qrcode`/`code` from Evolution Go, while retaining support for legacy `Qrcode`/`Code`, with or without the `data` envelope. Four response-contract assertions passed against the generated controller; all 27 ops tests passed.

The CRM image job completed successfully and its manifest was verified by anonymous registry retrieval and SHA-256. Only `CRM_IMAGE` was updated in Coolify, followed by the service stack's **Restart (pull latest)** operation. This also updates the CRM Sidekiq container, which uses the same variable.

## Runtime verification

- The deployed `app/controllers/api/v1/evolution_go/qrcodes_controller.rb` has SHA-256 `a4c96204c0fcc7f37960e519d66949d350de1a464b5f9208832a1e262c20256a`, matching the tested build context.
- Coolify reports CRM and CRM Sidekiq `Running (healthy)`.
- The frontend stayed available. The API briefly returned 503/502 during the restart, then returned 200 in four successive checks from 05:30:15Z through 05:31:02Z.
- The actual channel QR refresh and WhatsApp pairing remain to be tested by the user.

This CRM-only promotion supersedes the CRM image entry in the earlier full-stack release lock. Other image references were not promoted from this build.
