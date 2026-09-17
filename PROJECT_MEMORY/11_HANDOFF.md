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
- testes adversariais anteriores permanecem: adulteração de chave, revogação terminal, replay de sessão, hash de segredo e concorrência de device binding;
- endpoints administrativos exigem autenticação e `ADMIN`, com validação de payload e sem exposição do hash do dispositivo.

## Autenticação/sessões

- Argon2id para senha;
- senha mínima de 12 caracteres;
- tokens bearer aleatórios, armazenados somente como SHA-256 no servidor;
- sessões possuem expiração e revogação server-side;
- vida padrão de sessão atual: 12 horas;
- relógio do servidor usado na validade da sessão/licença.

## Validação

As alterações são enviadas diretamente ao `main`. A suíte local não está disponível neste ambiente porque o checkout não é montado aqui e o ambiente de execução não possui acesso de rede para clonar o GitHub. A validação definitiva deve usar os workflows do GitHub Actions e não deve ser declarada verde sem conclusão observável.

No momento do último registro, o workflow backend referente ao SHA `9d9f36beb08748089252274c120048a9f057a61f` ainda estava `in_progress`; o frontend desse SHA já havia concluído com sucesso. Um run anterior do backend (`35222409044`) havia falhado antes do hardening atual, portanto não deve ser usado como evidência de estado final.

## Próxima etapa obrigatória

1. Confirmar conclusão do CI backend e corrigir qualquer regressão real.
2. Fechar revisão de abuso administrativo, isolamento entre contas e vazamento de dados sensíveis.
3. Revisar limites administrativos e rate limiting; proteção distribuída de produção deve ficar no gateway/VPS, não em um contador local disfarçado de solução distribuída.
4. Integrar binding no Android no fluxo real de login/licença.
5. Implementar PIX de produção com provedor e webhook autenticado.
6. Implementar backup/restauração do licenciamento e executar teste real de restore.
7. Avançar para VPS, HTTPS, OSRM e DB de produção.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
