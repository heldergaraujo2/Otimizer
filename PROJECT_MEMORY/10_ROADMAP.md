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
**EM ANDAMENTO — núcleo comercial, persistência, dispositivos, ciclo de vida, API administrativa protegida, painel web, atomicidade e proteção contra lost updates implementados; integração Android e produção ainda pendentes.**

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
- rollback testado quando a inserção do evento falha;
- proteção otimista contra estado obsoleto em transições concorrentes: status anterior é validado dentro da transação e renovações também validam contador + expiração esperados;
- testes concorrentes determinísticos para ativação, renovação e revogação;
- revogação de dispositivo com auditoria atômica em SQLite.

### Subfase de segurança adversarial — progresso atual

A suíte `backend/tests/test_licensing_security_adversarial.py` cobre manipulação de chave, revogação terminal, replay de sessão, hash de segredo e concorrência do limite de dispositivos.

`backend/tests/test_license_atomicity.py` verifica que uma transição não permanece aplicada quando o registro de auditoria falha e que uma transição normal gera estado + histórico juntos.

`backend/tests/test_license_concurrency.py` força uma leitura concorrente do mesmo estado e verifica que somente uma operação vence, sem lost update e sem duplicação do evento de auditoria.

### Próxima subfase do licenciamento

1. Confirmar CI backend após o hardening e corrigir qualquer regressão.
2. Fechar revisão de abuso administrativo, isolamento entre contas e vazamento de dados sensíveis.
3. Revisar rate limiting, sessões/tokens e limites administrativos; rate limiting distribuído de produção deverá ficar no gateway/VPS quando o backend for implantado.
4. Integrar binding no Android no fluxo real de login/licença.
5. PIX de produção com provedor e webhook autenticado.
6. Backup/restauração do licenciamento com teste real de restore.
7. Depois disso, avançar para arquitetura/VPS/HTTPS/OSRM/DB de produção e testes completos pela Internet.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, backup/restore, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
