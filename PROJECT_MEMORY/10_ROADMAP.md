# Roadmap — OTIMIZER

## Objetivo final

Transformar XLSX reais de entregas em uma rota confiável, preservando todas as entregas válidas, identificando propriedades/paradas físicas, resolvendo localização com as melhores evidências disponíveis, roteando pela malha viária real e entregando uma sequência navegável ao motorista.

Fluxo-alvo:
`XLSX → Delivery → evidências → localização → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Estado das fases

### Fases 1–9 — núcleo funcional
**CONCLUÍDAS conforme registros anteriores; robustez/produção ainda pendentes.**

Importação, PhysicalStop, localização cadastral/fallback, OSRM, otimização, FastAPI, frontend, autenticação/licenciamento base e Android foram construídos e validados conforme os registros do projeto, incluindo mais de 30 XLSX reais e primeiro teste Android físico pela LAN.

### Fase 10 — Robustez e produção técnica
**EM ANDAMENTO**

CI/regressões, carga, falhas externas, segurança, deploy remoto, Android pela Internet, backup/restauração e monitoramento permanecem pendentes.

### Fase 11 — Sistema oficial de licenças
**EM ANDAMENTO — núcleo comercial, persistência, dispositivos, ciclo de vida, API administrativa protegida, painel web e primeira camada transacional implementados; hardening e produção ainda pendentes.**

Milestones implementados:

- estados `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`;
- `license_key` de alta entropia, distinto do ID interno;
- plano, ativação, renovação, contador e último acesso;
- eventos de auditoria persistentes;
- roles `USER`/`ADMIN`;
- migração aditiva do SQLite legado;
- unicidade da chave no banco;
- binding persistente de dispositivos;
- hash do segredo da instalação;
- enforcement server-side de `max_devices`;
- reuso do mesmo dispositivo sem consumir slot;
- revogação de dispositivo;
- serviço de ciclo de vida para ativação, renovação, suspensão, reativação, revogação e expiração;
- transições inválidas bloqueadas e revogação permanente;
- expiração baseada no relógio do servidor;
- auditoria de transições;
- API administrativa protegida por `AccountRole.ADMIN`;
- geração, consulta, ativação, renovação, suspensão, reativação e revogação por API;
- listagem/detalhes/histórico de licenças;
- listagem e revogação de dispositivos;
- painel administrativo dedicado em `frontend/admin.html`, com login ADMIN, métricas, filtros, geração, detalhes, ciclo de vida, dispositivos e histórico;
- navegação para administração no app principal somente para contas `ADMIN`;
- CI frontend ampliado para validar o novo painel;
- respostas administrativas sem expor segredos de instalação;
- `save_with_event()` em SQLite para persistir licença + auditoria em uma transação única;
- rollback testado quando a inserção do evento falha.

### Subfase de segurança adversarial — progresso atual

Foi adicionada uma suíte específica em `backend/tests/test_licensing_security_adversarial.py` cobrindo manipulação de chave, revogação terminal, replay de sessão, hash de segredo e concorrência do limite de dispositivos.

Foi adicionada `backend/tests/test_license_atomicity.py` para verificar que uma transição não permanece aplicada quando o registro de auditoria falha e que uma transição normal gera estado + histórico juntos.

### Próxima subfase do licenciamento

1. Observar CI e corrigir qualquer regressão introduzida pela camada transacional.
2. Completar testes concorrentes específicos de ativação/renovação/revogação e impedir lost updates.
3. Completar testes de abuso dos endpoints administrativos, isolamento entre contas e não vazamento de dados sensíveis.
4. Revisar rate limiting, sessões/tokens e limites administrativos.
5. Integrar binding no Android no fluxo real de login/licença.
6. PIX de produção com provedor e webhook autenticado.
7. Backup/restauração do licenciamento com teste real de restore.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, backup/restore, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
