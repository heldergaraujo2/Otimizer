# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado atual

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend e primeiro fluxo Android físico está validado conforme registros anteriores. O projeto entrou na etapa de robustez, produção e conclusão do sistema comercial de licenças.

## Licenciamento — auditoria concluída

A auditoria comparou o código existente com a especificação oficial do Sistema de Licenças.

### Já existia e foi preservado

- `License` com validade baseada em tempo do servidor.
- `Entitlements` para recursos e limites.
- autenticação por conta/sessão.
- Argon2 para senhas.
- bearer session token com hash persistido.
- autorização server-side antes de `/optimize`.
- SQLite para contas, sessões, licenças e pagamentos.
- `/licenses/me`.
- PIX sandbox e settlement idempotente/atômico.
- testes de licença ativa, expirada, revogada, entitlement e API.

### Gaps identificados

- máquina de estados comercial completa;
- chave comercial separada do ID interno;
- histórico/auditoria de transições;
- role administrativo;
- dispositivos e binding;
- enforcement de `max_devices`;
- ativação formal;
- suspensão/reativação formal;
- renovação administrativa com histórico;
- endpoints administrativos;
- painel administrativo;
- dashboard/filtros/detalhes;
- PIX de produção/webhook autenticado;
- testes adversariais, concorrência, manipulação, backup/restore e escalabilidade.

## Milestone implementado após a auditoria

### Núcleo comercial da licença

`backend/src/otimizer_api/licensing.py` agora contém:

- `LicenseStatus`: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`;
- `license_key` de alta entropia, separado de `license_id`;
- plano;
- `activated_at`;
- `last_renewal_at`;
- `renewal_count`;
- `last_access_at`;
- `effective_status()` usando hora do servidor;
- validações de limites;
- `LicenseEvent` imutável e repositório em memória;
- gerador seguro de chave.

`backend/src/otimizer_api/accounts.py` agora possui `AccountRole` com `USER` e `ADMIN`, preparando RBAC sem alterar o comportamento padrão das contas existentes.

Testes adicionados em `backend/tests/test_license_lifecycle_primitives.py` cobrindo:

- unicidade/entropia mínima da chave;
- compatibilidade do estado ativo;
- expiração por tempo do servidor;
- suspensão;
- revogação exigindo timestamp;
- limites de entitlement;
- evento de auditoria.

## Commits deste avanço

- `3058a0fd50d70901d82cd02e82900673db944856` — núcleo comercial da licença.
- `6b1a2f4c6db0fc15904c4835bbce234dbbbcdeab` — roles de conta.
- `0f2fe7331f91015068f04269517b443f8e3f6ad8` — testes do núcleo.
- `671c2592cef433422584296756c0e5b604ae000f` — atualização do roadmap.
- este commit — atualização do handoff.

## CI

Os pushes acionaram os workflows do GitHub Actions. No momento da última consulta, os workflows Backend e Frontend do commit de testes ainda estavam `in_progress`; portanto não declarar verde até nova verificação posterior.

## Próxima etapa obrigatória

A próxima alteração deve ser **persistência compatível e migração segura**:

1. adicionar ao SQLite os novos campos de licença e role;
2. preservar bancos existentes;
3. persistir `license_key` com unicidade;
4. persistir status, plano, ativação, renovação e demais metadados;
5. criar tabela de histórico/auditoria;
6. criar testes de migração, leitura/escrita e compatibilidade com dados antigos.

Depois disso:

`dispositivos/binding → serviço transacional de ciclo de vida → endpoints admin → painel → segurança adversarial → PIX produção → backup/restore`.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
