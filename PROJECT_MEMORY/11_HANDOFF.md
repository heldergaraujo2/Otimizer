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

`LicenseLifecycleService` centraliza as transições comerciais:

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

### API administrativa — concluída nesta etapa

`backend/src/otimizer_api/admin_api.py` adiciona uma camada HTTP exclusiva para administradores:

- autenticação Bearer obrigatória;
- `AccountRole.ADMIN` obrigatório; usuário comum recebe `403`;
- geração de licença com plano, duração, preço e entitlements;
- consulta/listagem com filtros por conta/status;
- detalhes individuais;
- ativação, renovação, suspensão, reativação e revogação;
- histórico completo de eventos;
- listagem de dispositivos;
- revogação administrativa de dispositivo;
- hash/segredo de instalação não é retornado pela API;
- eventos registram o administrador responsável.

A API está conectada ao `app` de produção em `main.py`, usando os repositórios SQLite e `LicenseLifecycleService`.

### Testes adicionados

`backend/tests/test_admin_license_api.py` cobre:

- acesso sem autenticação (`401`);
- usuário `USER` impedido (`403`);
- administrador autorizado;
- geração, consulta e histórico;
- ciclo completo de ativação → suspensão → reativação → renovação → revogação;
- bloqueio de reativação após revogação;
- listagem e revogação de dispositivo;
- ausência de `device_key_hash` nas respostas administrativas.

## Commits deste avanço

- `640284c46c6db8fe7cb78440cb57661366272ef3` — API administrativa inicial.
- `967a5eb3e15525750205c4b0f7633fa8efa0d302` — testes da API administrativa.
- `152a42dafcc5cb5b6595384bc6a9f7aa0c2aa032` — compatibilidade da listagem com repositórios existentes.
- `efef65412de5ec50b13c7036b8939f5fafd03153` — integração da API no app de produção.
- `9b9a92613a8b4200c79d1464c62d7188a10cb476` — atualização do roadmap após o milestone.

## Validação e ressalva

O HEAD atual contém a integração e os testes. A execução local não está disponível neste ambiente. As Actions anteriores confirmaram sucesso em parte das alterações intermediárias, mas o commit de integração criado via Git data API não recebeu execução automática observável pelo conector. Portanto, não declarar a suíte completa verde sem uma execução do CI no HEAD atual.

Também permanece uma ressalva arquitetural: algumas transições do `LicenseLifecycleService` salvam a licença e depois registram o evento em operações separadas. A atomicidade licença + auditoria deve ser endurecida na próxima revisão de segurança/concorrência antes de produção comercial.

## Próxima etapa obrigatória

**Painel administrativo real sobre a API protegida.** Depois:

1. painel de métricas/listagem/filtros/detalhes/histórico;
2. segurança adversarial, abuso e concorrência;
3. integração Android do binding com login/licença;
4. PIX de produção com webhook autenticado;
5. backup/restore do licenciamento;
6. VPS/produção.

## Regras de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Sempre seguir:

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
