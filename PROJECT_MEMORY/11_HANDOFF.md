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
- serviço de ciclo de vida com relógio do servidor;
- API administrativa protegida por `AccountRole.ADMIN`;
- geração, consulta/filtros, detalhes, ativação, renovação, suspensão, reativação, revogação;
- gestão de dispositivos e histórico;
- painel administrativo web dedicado;
- navegação para o painel no app principal somente para `ADMIN`;
- CI frontend inclui sintaxe e testes do painel.

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

O ajuste do fixture adversarial foi enviado no SHA `087f1cc5615b5898bc027a6ba61b8138a734c86b`. O workflow Backend tests desse SHA concluiu `success`, assim como o workflow Frontend tests correspondente. Esta é a evidência atual de que a regressão observada foi corrigida.

A suíte local continua não disponível neste ambiente porque o checkout não é montado aqui; a validação definitiva deste ciclo foi feita pelo GitHub Actions.

## Próxima etapa obrigatória

1. Fechar a integração de binding de dispositivo no Android: gerar/armazenar segredo por instalação com Android Keystore, autenticar no backend e vincular ao limite da licença.
2. Fazer o fluxo de uso depender da autorização do dispositivo, sem confiar somente na licença da conta.
3. Testar instalação/reinstalação, segundo dispositivo, limite, revogação e sessão expirada.
4. Depois, implementar PIX de produção com provedor e webhook autenticado.
5. Implementar backup/restauração do licenciamento e executar teste real de restore.
6. Avançar para VPS, HTTPS, OSRM e DB de produção.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
