# Roadmap — OTIMIZER

## Objetivo final

Transformar XLSX reais de entregas em uma rota confiável, preservando todas as entregas válidas, identificando propriedades/paradas físicas, resolvendo localização com as melhores evidências disponíveis, roteando pela malha viária real e entregando uma sequência navegável ao motorista.

Fluxo-alvo:
`XLSX → Delivery → evidências → localização → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Estado das fases

### Fases 1–9 — núcleo funcional
**CONCLUÍDAS conforme histórico e estado atual do repositório; robustez/produção ainda pendentes.**

Importação, PhysicalStop, localização cadastral/fallback, OSRM, otimização, FastAPI, frontend, autenticação/licenciamento base e Android foram construídos. O histórico registra validação com mais de 30 XLSX reais e primeiro teste Android físico pela LAN.

### Fase 10 — Robustez e produção técnica
**EM ANDAMENTO.**

CI/regressões, testes físicos completos do Android, falhas externas, backup/restauração, deploy remoto, Android pela Internet e monitoramento permanecem pendentes.

**Backup/restore provider-neutral: IMPLEMENTAÇÃO TÉCNICA INICIADA.**

Foi adicionado `backend/src/otimizer_api/backup.py`, integrado ao desenho atual de persistência SQLite, com:

- snapshot usando a API nativa de backup do SQLite;
- escrita atômica via arquivo temporário + replace;
- manifest JSON versionado;
- SHA-256 do snapshot;
- validação de `PRAGMA integrity_check`;
- validação das tabelas críticas `accounts`, `sessions`, `licenses`, `license_events` e `payments`;
- conferência dos contadores registrados no manifest;
- permissões locais `0600` para os artefatos criados;
- restore validado para arquivo-alvo separado e substituição atômica somente após validação;
- falha de validação não substitui um alvo existente.

Foram adicionados testes em `backend/tests/test_backup.py` cobrindo round-trip, integridade, manifest ausente, adulteração, proteção do alvo e prevenção de backup sobre o próprio banco.

**Importante:** isto ainda não é um sistema de backup de produção. Retenção, armazenamento externo/imutável, criptografia em repouso conforme o ambiente, agenda operacional, monitoramento, execução de restore real e prova de recuperação continuam pendentes.

### Fase 11 — Sistema oficial de licenças
**EM ANDAMENTO — núcleo comercial e controles de segurança implementados; produção comercial ainda pendente.**

Milestones implementados:

- estados `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`;
- `license_key` de alta entropia, distinto do ID interno;
- plano, ativação, renovação, contador, último acesso e entitlements;
- eventos de auditoria persistentes;
- roles `USER`/`ADMIN`;
- migração aditiva do SQLite legado;
- unicidade da chave no banco;
- binding persistente de dispositivos;
- hash do segredo da instalação;
- enforcement server-side de `max_devices`;
- reuso do mesmo dispositivo sem consumir slot;
- revogação terminal do binding;
- segredo Android protegido por Android Keystore e armazenado cifrado;
- endpoint autenticado `/devices/bind` sem retorno do segredo/hash;
- fallback de identidade de instalação no navegador;
- autorização server-side de `/optimize` e `/optimize-manual` por `X-Otimizer-Device-ID` quando o repositório de dispositivos está ativo;
- revogação do dispositivo bloqueia uso posterior;
- serviço de ciclo de vida para ativação, renovação, suspensão, reativação, revogação e expiração;
- transições inválidas bloqueadas e expiração baseada no relógio do servidor;
- API administrativa protegida por `AccountRole.ADMIN`;
- geração, consulta/filtros, detalhes, ativação, renovação, suspensão, reativação e revogação;
- gestão e revogação de dispositivos;
- painel administrativo em `frontend/admin.html`/`admin.js`/`admin.css`;
- navegação administrativa no app principal somente para `ADMIN`;
- CI frontend inclui sintaxe e testes do painel;
- `save_with_event()` com transação SQLite e rollback em falha de auditoria;
- proteção contra estado obsoleto/lost update em transições concorrentes;
- testes adversariais e concorrentes;
- revogação de dispositivo com auditoria atômica.

### Subfase PIX — fundação de segurança implementada

`backend/src/otimizer_api/pix_webhook.py` fornece primitives provider-neutral:

- HMAC-SHA256 sobre `timestamp + '.' + raw_body`;
- janela temporal contra replay;
- comparação em tempo constante;
- suporte a `sha256=`;
- validação estrita de `event_id`, `payment_id`, `amount_cents` e status;
- testes em `backend/tests/test_pix_webhook.py`.

**Não é Pix de produção concluído.** Ainda falta selecionar/configurar o PSP real, implementar seu adaptador conforme documentação oficial, ligar o endpoint à `PaymentService`, persistir idempotência, impedir dupla liquidação e homologar com sandbox/credenciais reais.

## Verificação deste ciclo — 2026-09-17

- HEAD de continuidade anterior: `b346edc61c49dbf02d8dbae464d064e9e3c83239`.
- Nesta etapa foram adicionados `backup.py` e `test_backup.py`; a sequência resultante ficou nos commits `719039bb48b54680bb9ad76b086ee2d441ab938c` e `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380`.
- A persistência atual usa SQLite e contém as tabelas críticas cobertas pelo componente de backup.
- O ambiente do agente não possui checkout local montado; portanto, os testes não foram executados localmente nesta etapa.
- Não há execução de GitHub Actions observável para o commit `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380` e o combined status retornou vazio. Logo, a suíte Backend ainda não é declarada verde neste ciclo.
- A implementação foi limitada ao domínio provider-neutral de backup/restore; não houve alteração no roteador, localização, otimização, Android, licenciamento ou integração Pix específica.

## Próximas etapas obrigatórias

1. Executar fisicamente Android conforme `docs/ANDROID_HOMOLOGATION.md`.
2. Completar retenção, armazenamento externo seguro, agendamento e observabilidade de backups.
3. Executar restore real em ambiente controlado e validar dados críticos + inicialização da aplicação.
4. Definir política de sessões após restore; por segurança operacional, reautenticação/invalidação de sessões restauradas deve ser tratada explicitamente antes de produção.
5. Selecionar/configurar PSP Pix real e implementar adaptador + endpoint autenticado/idempotente.
6. Testar pagamento confirmado → liquidação → ativação/renovação da licença.
7. Preparar VPS, DB, OSRM, domínio e HTTPS.
8. Testar Android pela Internet, monitoramento e usuários piloto.
9. Gerar APK Release assinado, testar instalação limpa e executar auditoria final.

## Dependências que não devem ser inventadas

- PSP Pix real ainda não foi identificado no repositório; nenhuma integração específica deve ser criada assumindo um provedor.
- Testes físicos Android exigem dispositivo/ambiente de execução real.
- Credenciais de produção, domínio e infraestrutura só podem ser configurados com valores reais fornecidos/gerados no ambiente apropriado.

## Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes e verificadas, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, Pix homologado, backup/restore comprovado, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
