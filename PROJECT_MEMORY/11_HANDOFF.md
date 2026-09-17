# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado atual

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend e primeiro fluxo Android físico está validado conforme registros anteriores. O projeto está na etapa de robustez/produção e conclusão do sistema comercial de licenças.

## Licenciamento — auditoria e implementação

A auditoria encontrou uma base existente de autenticação, validade server-side, entitlements, SQLite, `/licenses/me`, autorização do `/optimize` e PIX sandbox. O trabalho novo foi acoplado a essa base sem substituir o núcleo funcional.

### Núcleo comercial implementado

- `LicenseStatus`: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`.
- `license_key` de alta entropia, separado do `license_id` interno.
- plano, ativação, renovação, contador de renovações e último acesso.
- `effective_status()` dependente do relógio do servidor.
- validação de limites de entitlement.
- `LicenseEvent` imutável e repositório de eventos em memória.
- `AccountRole`: `USER`/`ADMIN`.

### Persistência/migração implementada

`backend/src/otimizer_api/persistence.py` agora:

- persiste `Account.role`;
- persiste `license_key`, status, plano, ativação, renovação, contador e último acesso;
- cria índice único para `license_key`;
- cria `license_events` persistente com índice por licença/data;
- lê e grava todos os novos campos;
- mantém o schema legado por migração aditiva;
- preenche chaves ausentes de licenças legadas antes de aplicar unicidade;
- preserva os dados antigos em vez de recriar/apagar tabelas;
- mantém autenticação, `/licenses/me`, autorização de rota e PIX sandbox na mesma arquitetura;
- settlement PIX incrementa renovação e mantém a licença ativa de forma persistida.

### Testes adicionados

`backend/tests/test_license_lifecycle_primitives.py` cobre o núcleo de estados/chave/eventos.

`backend/tests/test_persistence_licensing_migration.py` cobre:

- persistência de role administrativo;
- persistência dos campos comerciais;
- unicidade de `license_key` no SQLite;
- persistência e ordenação do histórico;
- migração de banco legado sem perda dos dados essenciais.

## Commits recentes

- `3058a0fd50d70901d82cd02e82900673db944856` — núcleo comercial da licença.
- `6b1a2f4c6db0fc15904c4835bbce234dbbbcdeab` — roles de conta.
- `0f2fe7331f91015068f04269517b443f8e3f6ad8` — testes do núcleo.
- `671c2592cef433422584296756c0e5b604ae000f` — documentação inicial do milestone.
- `c7b538b0efdd95f6b6bc931fc7aef44c7db3a438` — handoff do milestone inicial.
- `a351e8eb343293a40c6a00d2c3999eff8bd6b14c` — persistência comercial/migração.
- `9cbf64e30ceb3fc0afb44fe1fe5763c14458a138` — testes de migração/persistência.
- `81a4a2393ca7ca14d87504bba778ad06a6f125cb` — roadmap atualizado.

## Validação e ressalva

As alterações foram gravadas diretamente no `main` pelo GitHub e os pushes acionaram CI. A execução local não está disponível neste ambiente; portanto, os novos testes não devem ser apresentados como executados localmente. A situação dos workflows deve ser verificada no GitHub antes de declarar a suíte verde.

## Próxima etapa obrigatória

**Dispositivos e binding de licença.** Implementar, testar e revisar:

1. entidade persistente de dispositivo com identificador seguro, conta/licença e timestamps;
2. registro/ativação do dispositivo no backend;
3. enforcement de `max_devices` no servidor;
4. impedir que alteração no APK ou relógio local contorne o limite;
5. eventos de registro, vinculação, desvinculação e rejeição;
6. testes de primeiro dispositivo, limite, excesso, reuso, concorrência e persistência.

Depois:

`serviço transacional de ciclo de vida → endpoints admin → painel → segurança adversarial → PIX produção → backup/restore → produção/VPS`.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
