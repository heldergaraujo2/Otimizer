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
- serviço de ciclo de vida com relógio do servidor;
- API administrativa protegida por `AccountRole.ADMIN`;
- geração, consulta/filtros, detalhes, ativação, renovação, suspensão, reativação, revogação;
- gestão de dispositivos e histórico;
- painel administrativo web dedicado;
- navegação para o painel no app principal somente para `ADMIN`;
- CI frontend inclui sintaxe e testes do painel.

## Segurança e atomicidade — implementado nesta iteração

- `LicenseLifecycleService` agora centraliza o commit de transições e usa `save_with_event` quando o repositório durável oferece suporte transacional;
- `SQLiteLicenseRepository.save_with_event()` usa `BEGIN IMMEDIATE` e grava licença + evento na mesma transação;
- falha na gravação do evento provoca rollback da mudança de licença;
- adicionados testes de atomicidade/rollback em `backend/tests/test_license_atomicity.py`;
- testes adversariais anteriores permanecem: adulteração de chave, revogação terminal, replay de sessão, hash de segredo e concorrência de device binding.

## Validação

As alterações foram enviadas diretamente ao `main`. A suíte local não está disponível neste ambiente; a validação definitiva deve usar os workflows do GitHub Actions e não deve ser declarada verde sem conclusão observável.

## Próxima etapa obrigatória

**Hardening final do licenciamento**, nesta ordem:

1. observar e corrigir eventuais falhas do CI após a mudança transacional;
2. testes concorrentes específicos de ativação/renovação/revogação para impedir lost update;
3. abuso, enumeração, isolamento entre contas e vazamento nos endpoints administrativos;
4. revisão de rate limiting, sessões/tokens e limites administrativos;
5. integração Android do binding no fluxo real de login/licença;
6. PIX de produção com provedor/webhook autenticado;
7. backup/restore com teste real.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
