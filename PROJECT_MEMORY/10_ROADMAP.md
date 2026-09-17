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
**EM ANDAMENTO — núcleo comercial, persistência, dispositivos, ciclo de vida, API administrativa protegida, painel web, atomicidade, concorrência e integração de binding cliente-servidor implementados; produção comercial ainda pendente.**

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
- revogação permanente do binding;
- segredo Android protegido por Android Keystore e persistido cifrado;
- endpoint autenticado `/devices/bind` sem retorno do segredo/hash;
- browser também possui identidade de instalação aleatória persistida localmente;
- autorização server-side das rotas por `X-Otimizer-Device-ID` quando o app global usa o repositório de dispositivos;
- rota manual também exige binding de dispositivo;
- revogação do dispositivo bloqueia nova tentativa com o mesmo segredo;
- serviço de ciclo de vida para ativação, renovação, suspensão, reativação, revogação e expiração;
- transições inválidas bloqueadas e revogação terminal;
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
- proteção otimista contra estado obsoleto em transições concorrentes;
- testes concorrentes determinísticos para ativação, renovação e revogação;
- revogação de dispositivo com auditoria atômica em SQLite.

### Subfase de segurança adversarial — progresso atual

A suíte `backend/tests/test_licensing_security_adversarial.py` cobre manipulação de chave, revogação terminal, replay de sessão, hash de segredo e concorrência do limite de dispositivos.

`backend/tests/test_license_atomicity.py` verifica que uma transição não permanece aplicada quando o registro de auditoria falha e que uma transição normal gera estado + histórico juntos.

`backend/tests/test_license_concurrency.py` força uma leitura concorrente do mesmo estado e verifica que somente uma operação vence, sem lost update e sem duplicação do evento de auditoria.

`backend/tests/test_device_binding_api.py` e `backend/tests/test_device_authorization.py` cobrem autenticação, limite, reuso, revogação, isolamento e bloqueio server-side da rota sem binding válido.

### Próxima subfase do licenciamento

1. Confirmar CI backend após o hardening de device binding e corrigir qualquer regressão real.
2. Testar reinstalação/restore de dados, segundo dispositivo, limite, revogação e sessão expirada em ambiente Android físico.
3. Implementar PIX de produção com provedor e webhook autenticado.
4. Implementar backup/restauração do licenciamento e executar teste real de restore.
5. Avançar para arquitetura/VPS/HTTPS/OSRM/DB de produção e testes completos pela Internet.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, backup/restore, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
