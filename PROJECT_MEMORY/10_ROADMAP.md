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

**Backup/restore provider-neutral: fundação implementada.**

`backend/src/otimizer_api/backup.py` fornece snapshot SQLite, manifest versionado, SHA-256, `PRAGMA integrity_check`, validação de tabelas/contagens críticas, publicação atômica, restore atômico e retenção configurável. `backend/tests/test_backup.py` cobre round-trip, adulteração, manifest ausente, proteção do alvo e retenção. `docs/BACKUP_RESTORE.md` documenta o runbook.

Isso ainda **não** é backup/restore de produção: destino externo/imutável, criptografia de armazenamento, agendamento, alertas, RPO/RTO e exercício real de recuperação continuam pendentes.

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
- gestão de licenças e dispositivos;
- painel administrativo;
- `save_with_event()` transacional;
- proteção contra estado obsoleto/lost update;
- testes adversariais e concorrentes;
- revogação de dispositivo com auditoria atômica.

### Subfase PIX — fundação de segurança implementada

`backend/src/otimizer_api/pix_webhook.py` fornece primitives provider-neutral: HMAC-SHA256, timestamp/anti-replay, comparação em tempo constante, `sha256=` e validação estrita de evento/pagamento/valor/status.

**Não é Pix de produção concluído.** Ainda falta PSP real, adaptador, endpoint específico, idempotência persistente, proteção contra dupla liquidação e homologação.

## Verificação deste ciclo — 2026-09-17

- Continuidade anterior: `b346edc61c49dbf02d8dbae464d064e9e3c83239`.
- Implementação backup: `719039bb48b54680bb9ad76b086ee2d441ab938c`.
- Testes backup: `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380`.
- Retenção: `eb4ecd77a298803b40f9ca5ab5b6edf12bf71ad`.
- Teste de retenção: `f8bc7b305dae3293ef460bd463ccfd7ac134212f`.
- Runbook: `0b6f51eecb3cb64063bf5cfb2c4a3fd4ea790f4b`.
- Documentação de continuidade/security foi atualizada nesta mesma sequência.
- O checkout local não está montado no ambiente do agente; testes locais não foram executados.
- Não há evidência observável pelo conector de CI Backend para estes commits; combined status observado anteriormente foi vazio. Portanto, Backend não é declarado verde.
- Nenhuma alteração foi feita no motor de localização, OSRM, otimização, Android, licenciamento ou integração Pix específica.

## Próximas etapas obrigatórias

1. Executar fisicamente Android conforme `docs/ANDROID_HOMOLOGATION.md`.
2. Criar prova automatizada de restore + boot da aplicação em ambiente controlado.
3. Homologar restore real em staging e validar dados críticos.
4. Definir/instrumentar invalidação ou reautenticação de sessões após restore.
5. Definir destino externo/imutável, criptografia, agendamento, alertas e RPO/RTO para produção.
6. Selecionar/configurar PSP Pix real e implementar adaptador + endpoint autenticado/idempotente.
7. Testar pagamento confirmado → liquidação → ativação/renovação da licença.
8. Preparar VPS, DB, OSRM, domínio e HTTPS.
9. Testar Android pela Internet, monitoramento e usuários piloto.
10. Gerar APK Release assinado, testar instalação limpa e executar auditoria final.

## Dependências que não devem ser inventadas

- PSP Pix real ainda não foi identificado no repositório.
- Testes físicos Android exigem dispositivo/ambiente real.
- Credenciais, domínio e infraestrutura de produção só podem ser configurados com valores reais no ambiente apropriado.

## Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes e verificadas, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, Pix homologado, backup/restore comprovado, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
