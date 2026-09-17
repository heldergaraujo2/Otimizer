# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado verificado em 2026-09-17

O repositório foi auditado antes de qualquer alteração. A `main` estava no commit `dab00fd7817300aec0dc750c68c552464e815554`, e a atualização documental desta auditoria foi aplicada em seguida no commit `70835fe4bfb7807b0c47bb3f925f3beb04aa6124`.

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend e primeiro fluxo Android físico está implementado. O projeto está na etapa de robustez/homologação e conclusão do sistema comercial.

## Documentação encontrada

Existem e foram consultados `PROJECT_MEMORY/00_IDENTITY.md`, `01_PRODUCT_VISION.md`, `02_REQUIREMENTS.md`, `08_CURRENT_STATE.md`, `10_ROADMAP.md`, `11_HANDOFF.md` e documentos relevantes de `docs/` (`REQUIREMENTS.md`, `ARCHITECTURE.md`, `XLSX_SPEC.md`).

Os caminhos `PROJECT_MEMORY/03_ARCHITECTURE.md`, `04_ROUTING_ENGINE.md`, `05_OPTIMIZATION.md`, `06_XLSX_FORMAT.md`, `07_ROADMAP.md`, `09_DECISIONS.md` e `PROJECT_MEMORY/10_TESTS.md`, assim como `docs/ROADMAP.md` e `docs/TESTING.md`, não existem na `main` atual (GitHub retornou 404). Não foram recriados automaticamente, pois isso exigiria inventar conteúdo histórico. A arquitetura disponível em `docs/ARCHITECTURE.md`, o README e os demais registros atuais foram usados como fonte.

## Licenciamento — estado implementado

- estados `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`;
- chave comercial de alta entropia separada do ID interno;
- plano, ativação, renovação, contador, último acesso e entitlements;
- histórico de auditoria persistente;
- roles `USER`/`ADMIN`;
- migração aditiva SQLite e unicidade da chave;
- binding persistente, hash de segredo e enforcement server-side de `max_devices`;
- mesmo dispositivo pode ser reutilizado sem consumir outro slot;
- dispositivo revogado não pode ser religado com o mesmo segredo;
- serviço de ciclo de vida com relógio do servidor;
- API administrativa protegida por `AccountRole.ADMIN`;
- geração, consulta/filtros, detalhes, ativação, renovação, suspensão, reativação, revogação;
- gestão de dispositivos e histórico;
- painel administrativo web dedicado;
- navegação para o painel no app principal somente para `ADMIN`;
- CI frontend inclui sintaxe e testes do painel.

## Integração de binding no cliente

- `POST /devices/bind` exige sessão autenticada e licença pertencente à conta;
- Android gera segredo aleatório por instalação;
- segredo Android é cifrado com chave AES armazenada no Android Keystore e não é exposto ao JavaScript nem ao backend em armazenamento persistente;
- resposta de binding expõe somente `device_id` e estado, nunca o segredo/hash;
- frontend Android bloqueia otimização até o binding ser confirmado;
- navegador possui fallback com segredo aleatório persistido no armazenamento local;
- `/optimize` e `/optimize-manual` aceitam `X-Otimizer-Device-ID`;
- a aplicação global instancia `SQLiteDeviceRepository` e valida no servidor conta, dispositivo ativo e licença ativa antes de processar a rota;
- revogação de dispositivo impede uso posterior mesmo com licença ativa;
- testes específicos cobrem endpoint de binding e autorização da rota.

## Segurança, atomicidade e concorrência

- `LicenseLifecycleService` centraliza transições e usa `save_with_event` quando o repositório durável oferece suporte transacional;
- `SQLiteLicenseRepository.save_with_event()` usa `BEGIN IMMEDIATE` e grava licença + evento na mesma transação;
- falha na gravação do evento provoca rollback da mudança de licença;
- `LicenseConcurrencyError` impede que uma operação baseada em leitura obsoleta sobrescreva uma transição concorrente;
- ativações/suspensões/reativações/revogações/expirações validam o status anterior dentro da transação;
- renovações validam `renewal_count` e `expires_at` esperados;
- testes concorrentes cobrem ativação, renovação e revogação;
- revogação de dispositivo em SQLite pode persistir alteração + auditoria na mesma transação;
- endpoints administrativos exigem autenticação e `ADMIN`, sem exposição do hash do dispositivo.

## Autenticação/sessões

- Argon2id para senha;
- senha mínima de 12 caracteres;
- tokens bearer aleatórios, armazenados somente como SHA-256 no servidor;
- sessões possuem expiração e revogação server-side;
- vida padrão de sessão atual: 12 horas;
- relógio do servidor usado na validade da sessão/licença.

## PIX — fundação de produção adicionada

`backend/src/otimizer_api/pix_webhook.py` fornece primitives provider-neutral para autenticação de webhook:

- HMAC-SHA256 calculado sobre timestamp + corpo bruto;
- janela temporal configurável para rejeitar replay fora da tolerância;
- comparação em tempo constante;
- suporte a assinatura com prefixo `sha256=`;
- parser estrito de `event_id`, `payment_id`, `amount_cents` e status permitido;
- nenhum segredo de PSP fica no Android ou no repositório;
- `backend/tests/test_pix_webhook.py` cobre evento válido, prefixo, corpo adulterado, replay, campos ausentes e valores/status inválidos.

Esta etapa é somente a fundação de segurança. O Pix comercial **não deve ser considerado produção concluída** até que um PSP real seja escolhido/configurado, seu contrato de assinatura seja implementado no adaptador, o endpoint seja ligado à `PaymentService`, a idempotência de eventos seja persistida e a homologação real seja executada.

## CI — estado real

Os workflows existentes na `main` são:

- Backend tests;
- Frontend tests;
- Importer tests;
- Android APK.

O SHA atual antes desta documentação (`dab00fd...`) não possui workflow run observável pela integração GitHub disponível. Portanto, **CI não está declarado verde**. A suíte local também não está disponível neste ambiente porque o checkout não é montado aqui.

O histórico recente registra Backend + Frontend verdes no SHA `087f1cc5615b5898bc027a6ba61b8138a734c86b` e correções posteriores de binding/CORS. Isso é evidência histórica, não substituto para validar a `main` atual.

## Android — estado e limite de validação

O código atual contém geração e proteção do segredo por Android Keystore e configuração de API. O workflow `android-apk.yml` constrói um APK **debug**, não um release comercial.

Ainda é necessário executar em dispositivo real:

1. login → licença → binding → otimização;
2. revogar dispositivo no painel → confirmar bloqueio;
3. segundo dispositivo → confirmar `max_devices`;
4. reinstalação/restore → confirmar comportamento esperado do binding;
5. sessão expirada → confirmar bloqueio/reautenticação;
6. licença expirada/suspensa/revogada → confirmar bloqueio.

Esses testes não podem ser inventados nem considerados executados apenas por inspeção do código.

## Próxima etapa objetiva

A próxima etapa de engenharia dependente do usuário é a **homologação física Android** dos cenários acima. Enquanto o dispositivo real não estiver sendo executado, não alterar o núcleo de binding apenas para produzir testes artificiais.

Em paralelo, o próximo bloco de engenharia que pode ser implementado sem credenciais externas é **backup/restauração**, mas deve começar somente após registrar os cenários físicos de binding como executados ou explicitamente pendentes.

Depois:

1. selecionar/configurar PSP Pix real;
2. implementar adaptador e webhook real;
3. persistir idempotência e impedir dupla liquidação;
4. testar pagamento → licença;
5. backup + restore real;
6. VPS/DB/OSRM/HTTPS/domínio;
7. Android pela Internet;
8. monitoramento/pilotos;
9. APK Release assinado e instalação limpa;
10. auditoria final e Release Candidate.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
