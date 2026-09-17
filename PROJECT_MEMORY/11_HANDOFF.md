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

## Segurança adversarial — concluído nesta iteração

Foi criado `backend/tests/test_licensing_security_adversarial.py` com cobertura de:

- chave comercial não derivada do ID interno;
- tentativa de adulteração da chave sem mutação do registro autoritativo;
- revogação terminal;
- expiração server-side de sessão e rejeição de replay após expiração;
- segredo de dispositivo persistido somente como hash;
- concorrência de oito tentativas simultâneas contra `max_devices=1` em SQLite, garantindo somente um binding ativo.

## Validação CI

O commit desta suíte disparou os workflows do GitHub Actions. No momento do registro, o workflow de backend estava `in_progress` e o frontend estava `queued`; portanto, não declarar suíte verde até observar a conclusão.

## Ressalva crítica antes de produção

A atomicidade completa de **licença + auditoria** ainda não está concluída. O `LicenseLifecycleService` atualmente salva a licença e depois registra o evento em operações separadas. A próxima implementação deve colocar mudança de estado e evento na mesma transação e incluir teste de rollback para impedir estado comercial sem trilha de auditoria.

Também devem ser concluídos os testes de abuso/isolamento dos endpoints administrativos e a revisão de rate limiting aplicável.

## Próxima etapa obrigatória

**Hardening transacional do licenciamento**, nesta ordem:

1. transação única licença + evento;
2. rollback quando o evento falhar;
3. conflitos concorrentes em ativação/renovação/revogação;
4. abuso, enumeração, isolamento entre contas e vazamento nos endpoints administrativos;
5. somente depois, integração Android do binding.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque testes automatizados passaram.
