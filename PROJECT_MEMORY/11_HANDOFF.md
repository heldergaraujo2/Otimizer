# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado atual

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend e primeiro fluxo Android físico está validado conforme registros anteriores. O projeto está na etapa de robustez/produção e conclusão do sistema comercial de licenças.

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
- revogação de dispositivo passa a impedir uso posterior mesmo com licença ativa;
- testes específicos cobrem endpoint de binding e autorização da rota.

## Segurança, atomicidade e concorrência — estado atual

- `LicenseLifecycleService` centraliza o commit de transições e usa `save_with_event` quando o repositório durável oferece suporte transacional;
- `SQLiteLicenseRepository.save_with_event()` usa `BEGIN IMMEDIATE` e grava licença + evento na mesma transação;
- falha na gravação do evento provoca rollback da mudança de licença;
- `LicenseConcurrencyError` impede que uma operação baseada em leitura obsoleta sobrescreva uma transição concorrente;
- ativações/suspensões/reativações/revogações/expirações validam o status anterior dentro da transação;
- renovações também validam `renewal_count` e `expires_at` esperados;
- `backend/tests/test_license_concurrency.py` força a corrida de leitura e verifica um único vencedor/evento em ativação, renovação e revogação;
- revogação de dispositivo em SQLite pode persistir alteração + auditoria na mesma transação;
- testes adversariais cobrem adulteração de chave, revogação terminal, replay de sessão, hash de segredo e concorrência de device binding;
- endpoints administrativos exigem autenticação e `ADMIN`, com validação de payload e sem exposição do hash do dispositivo.

## Autenticação/sessões

- Argon2id para senha;
- senha mínima de 12 caracteres;
- tokens bearer aleatórios, armazenados somente como SHA-256 no servidor;
- sessões possuem expiração e revogação server-side;
- vida padrão de sessão atual: 12 horas;
- relógio do servidor usado na validade da sessão/licença.

## Validação CI

O SHA `087f1cc5615b5898bc027a6ba61b8138a734c86b` teve Backend tests e Frontend tests verdes após a correção do fixture adversarial.

Durante a implementação do binding, o Backend tests do SHA `4af5d80d45a5547f72225c78d88ac5698a24b298` encontrou quatro falhas reais: três causadas por um binding SQL incompleto no novo insert de dispositivo e uma por mapeamento HTTP do estado `DEVICE_REVOKED`. Essas falhas foram corrigidas em `dcfcb2a4dc401dbaca38736adfbe0f686d950d29` e `a620a2399ff6e3b19be2db5d2043acee61e60031`.

O Frontend tests do SHA `a620a2399ff6e3b19be2db5d2043acee61e60031` já concluiu `success`. O Backend tests desse mesmo SHA estava em execução no último checkpoint deste handoff; portanto, não declarar o ciclo verde até a conclusão observável.

A suíte local continua não disponível neste ambiente porque o checkout não é montado aqui; a validação definitiva deste ciclo deve usar o GitHub Actions.

## Próxima etapa obrigatória

1. Confirmar conclusão do Backend tests do SHA final e corrigir qualquer regressão restante.
2. Fazer teste físico Android de login → licença → binding → otimização e revogação/limite.
3. Testar reinstalação/restore, segundo dispositivo e sessão expirada.
4. Implementar PIX de produção com provedor e webhook autenticado.
5. Implementar backup/restauração do licenciamento e executar teste real de restore.
6. Avançar para VPS, HTTPS, OSRM e DB de produção.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
