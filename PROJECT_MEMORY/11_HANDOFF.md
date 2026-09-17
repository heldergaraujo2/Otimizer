# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado atual

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend e primeiro fluxo Android físico está validado conforme registros anteriores. O projeto está na etapa de robustez/produção e conclusão do sistema comercial de licenças.

## Licenciamento — estado implementado

A base existente de autenticação, validade server-side, entitlements, SQLite, `/licenses/me`, autorização do `/optimize` e PIX sandbox foi preservada.

### Núcleo comercial

- `LicenseStatus`: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`.
- `license_key` de alta entropia separado do `license_id` interno.
- plano, ativação, renovação, contador e último acesso.
- `effective_status()` dependente do relógio do servidor.
- `LicenseEvent` imutável e persistência de histórico.
- `AccountRole`: `USER`/`ADMIN`.

### Persistência e migração

- role, chave, estado, plano, ativação, renovação e último acesso persistidos.
- índice único para `license_key`.
- migração aditiva de schema legado sem apagar dados existentes.
- tabela `license_events` persistente.

### Dispositivos e binding — concluído

`backend/src/otimizer_api/devices.py` contém:

- `Device` vinculado a conta/licença, timestamps e revogação;
- hash SHA-256 do segredo da instalação; segredo bruto não é persistido;
- repositório em memória para testes e repositório SQLite para produção;
- índice único por `(license_id, device_key_hash)`;
- `DeviceBindingService` como autoridade server-side;
- reuso sem consumir slot adicional;
- enforcement de `max_devices`;
- revogação de dispositivo;
- bloqueio para licença expirada, suspensa ou revogada;
- capacidade + inserção protegidas pela mesma transação SQLite (`BEGIN IMMEDIATE`), reduzindo risco de corrida;
- eventos de registro, reuso, limite e revogação quando o repositório de eventos é fornecido.

### Serviço de ciclo de vida — concluído

`LicenseLifecycleService` agora centraliza as transições comerciais:

- `activate`: GERADA/DISPONIVEL → ATIVA;
- `renew`: estende validade a partir do maior entre expiração e horário do servidor;
- `suspend`: ATIVA → SUSPENSA, exigindo motivo;
- `reactivate`: SUSPENSA → ATIVA apenas se ainda válida;
- `revoke`: qualquer licença não revogada → REVOGADA, exigindo motivo e timestamp do servidor;
- `expire`: marca EXPIRADA somente após atingir a validade e é idempotente;
- revogação não pode ser reativada;
- expirada não pode ser ativada diretamente;
- suspensão não pode ser renovada pela operação normal;
- duração de renovação deve ser positiva;
- cada transição gera evento de auditoria;
- o relógio do cliente não participa da decisão.

### Testes

Além das suítes anteriores, `backend/tests/test_license_lifecycle_service.py` cobre ativação, repetição, suspensão/reativação, revogação permanente, expiração, renovação e validações de transição.

## Commits deste avanço

- `3947db7883007d6e4eb64a4a4fcec3fae3356218` — núcleo de device binding.
- `7f348fb2712259fe92d23086a65bbd1feb8590f2` — persistência/enforcement SQLite.
- `7c0dc614aabadb358240fb2d696d04a90eec0abc` — testes de dispositivos.
- `3306071e476a59b058e4017264f5ca3812596d6a` — roadmap/handoff do milestone.
- `4f8673b7b0444619b92c421140fc1e9c73625f52` — serviço de ciclo de vida.
- `c3ef3b42e7eeb510cf7aa2cd1995b2c68eb4958a` — testes do ciclo de vida.
- `2f2ebfd759fc77e75e74cf8fbf56a2e3456690b9` — roadmap atualizado.
- este commit — handoff atualizado.

## Validação e ressalva

As alterações estão no `main`. A execução local não está disponível neste ambiente. Não declarar a suíte verde sem confirmação do GitHub Actions para o HEAD atual.

## Próxima etapa obrigatória

**Endpoints administrativos protegidos por `AccountRole.ADMIN`.** Criar a camada HTTP sem expor operações comerciais a usuários comuns:

1. middleware/dependência de autenticação + role ADMIN;
2. geração e consulta de licenças;
3. ativação, renovação, suspensão, reativação e revogação;
4. gestão/listagem/revogação de dispositivos;
5. histórico/auditoria;
6. respostas sem vazar segredos internos;
7. testes de autorização USER vs ADMIN e abuso de endpoints.

Depois:

`painel admin → segurança adversarial → Android integrado ao binding → PIX produção → backup/restore → VPS/produção`.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
