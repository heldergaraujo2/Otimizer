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

### Dispositivos e binding — milestone concluído

`backend/src/otimizer_api/devices.py` agora contém:

- `Device` com vínculo a conta/licença, timestamps e revogação;
- hash SHA-256 do segredo da instalação; segredo bruto não é persistido;
- `InMemoryDeviceRepository` para testes;
- `SQLiteDeviceRepository` para persistência real;
- índice único por `(license_id, device_key_hash)`;
- `DeviceBindingService` como autoridade server-side;
- reuso do mesmo dispositivo sem consumir slot adicional;
- enforcement de `max_devices`;
- revogação de dispositivo;
- bloqueio para licença expirada, suspensa ou revogada;
- capacidade + inserção protegidas pela mesma transação SQLite (`BEGIN IMMEDIATE`), reduzindo risco de corrida no limite;
- eventos de registro, reuso, limite e revogação quando o repositório de eventos é fornecido.

### Testes

`backend/tests/test_devices.py` cobre:

- hash do segredo;
- primeiro dispositivo;
- limite de dispositivos;
- reuso sem consumir slot;
- licença suspensa/expirada/revogada;
- revogação liberando capacidade;
- persistência entre instâncias do repositório;
- enforcement no SQLite.

## Commits deste avanço

- `3947db7883007d6e4eb64a4a4fcec3fae3356218` — primeiro núcleo de device binding.
- `7f348fb2712259fe92d23086a65bbd1feb8590f2` — persistência e enforcement SQLite.
- `7c0dc614aabadb358240fb2d696d04a90eec0abc` — testes de dispositivos.
- `3306071e476a59b058e4017264f5ca3812596d6a` — roadmap atualizado.
- este commit — handoff atualizado.

## Validação e ressalva

As alterações estão no `main`. A execução local não está disponível neste ambiente. Os workflows/statuses do commit final ainda não retornaram resultados associados; portanto, não declarar a suíte verde sem confirmação posterior do GitHub Actions.

## Próxima etapa obrigatória

**Serviço transacional completo do ciclo de vida da licença.** Implementar com regras explícitas e atomicidade:

1. geração segura da licença;
2. disponibilidade sem ativação automática;
3. ativação por chave vinculada à conta/dispositivo;
4. renovação preservando histórico;
5. suspensão e reativação conforme regra administrativa;
6. revogação permanente, sem reativação trivial;
7. expiração baseada exclusivamente no servidor;
8. evento de auditoria para cada transição;
9. proteção contra concorrência e repetição de requisições.

Depois:

`endpoints admin → painel → segurança adversarial → Android integrado ao binding → PIX produção → backup/restore → VPS/produção`.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
