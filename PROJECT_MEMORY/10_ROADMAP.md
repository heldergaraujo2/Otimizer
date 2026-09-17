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

### Subfase PIX — fundação de produção implementada

Foi adicionada `backend/src/otimizer_api/pix_webhook.py`, uma camada provider-neutral para validar webhooks Pix antes de alterar pagamentos/licenças:

- HMAC-SHA256 sobre `timestamp + '.' + raw_body`;
- janela temporal configurável contra replay;
- comparação em tempo constante;
- suporte ao formato `sha256=`;
- validação estrita do evento, pagamento, valor e status;
- nenhuma credencial de PSP no APK ou no código-fonte;
- testes de assinatura válida, adulteração, replay, campos obrigatórios e status/valor inválidos em `backend/tests/test_pix_webhook.py`.

**Importante:** isto fecha a fundação de segurança do webhook, mas **não** significa que o Pix de produção esteja concluído. Ainda falta selecionar/configurar o PSP real, implementar o adaptador conforme a documentação oficial desse provedor, receber o webhook no endpoint da API, persistir idempotência por evento e executar homologação com credenciais reais.

### Próximas etapas obrigatórias

1. Confirmar GitHub Actions do ciclo após os commits de webhook e corrigir qualquer regressão.
2. Executar teste físico Android de login → licença → binding → otimização; revogar dispositivo pelo painel e confirmar bloqueio; validar segundo dispositivo/max_devices, reinstalação/restore e sessão expirada.
3. Escolher/configurar o PSP Pix real e ligar o adaptador ao fluxo assinado/idempotente.
4. Implementar backup/restauração do licenciamento e executar teste real de restore.
5. Avançar para arquitetura/VPS/HTTPS/OSRM/DB de produção e testes completos pela Internet.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, backup/restore, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
