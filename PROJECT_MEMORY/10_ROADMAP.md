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

- HEAD auditado inicialmente: `081b974aca5a0855e08be565a300c1eb52442817`.
- Esse commit é filho de `1b94079da362a3b71652aa35d3fa6a5fd63f30db` e contém a reconciliação do security audit com o binding Android já implementado.
- Os workflows existentes na `main` são Backend tests, Frontend tests, Importer tests e Android APK.
- Após o HEAD documental, o workflow `Frontend tests` executou no SHA `081b974aca5a0855e08be565a300c1eb52442817` e terminou `success` (run `35243638706`). As etapas de sintaxe JavaScript e testes frontend terminaram com sucesso.
- Os outros workflows não têm execução correspondente observável para esse SHA nesta auditoria, pois seus gatilhos de push possuem filtros de caminho que não incluem a documentação alterada. Portanto, Backend/Importer/Android não são declarados verdes neste ciclo.
- A suíte local não está disponível neste ambiente porque o checkout do repositório não é montado aqui.
- A implementação Android contém geração/proteção do segredo por Keystore e configuração de API, mas os cenários físicos de homologação continuam dependendo de execução em dispositivo real.
- Foi adicionada `docs/ANDROID_HOMOLOGATION.md` com a matriz oficial de homologação física do binding/licenciamento.

## Próximas etapas obrigatórias

1. Executar fisicamente Android conforme `docs/ANDROID_HOMOLOGATION.md`: instalação, login, licença, binding e otimização.
2. Revogar o dispositivo pelo painel e confirmar bloqueio da otimização.
3. Validar segundo dispositivo, `max_devices` e reuso do mesmo dispositivo.
4. Validar reinstalação/restore e comportamento do segredo/binding.
5. Validar licença expirada/suspensa/revogada e sessão expirada/novo login/revalidação.
6. Em paralelo, preparar tecnicamente backup/restore provider-neutral sem declarar restore real concluído.
7. Selecionar/configurar PSP Pix real e implementar adaptador + endpoint autenticado/idempotente.
8. Testar pagamento confirmado → liquidação → ativação/renovação da licença.
9. Executar restore real e validar integridade dos dados críticos.
10. Preparar VPS, DB, OSRM, domínio e HTTPS.
11. Testar Android pela Internet, monitoramento e usuários piloto.
12. Gerar APK Release assinado, testar instalação limpa e executar auditoria final.

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
