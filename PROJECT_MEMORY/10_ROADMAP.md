# Roadmap — OTIMIZER

## Objetivo final

Transformar XLSX reais de entregas em uma rota confiável, preservando todas as entregas válidas, identificando propriedades/paradas físicas, resolvendo localização com as melhores evidências disponíveis, roteando pela malha viária real e entregando uma sequência navegável ao motorista.

Fluxo-alvo:

`XLSX → Delivery → evidências → localização da propriedade → ponto de acesso → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Estado das fases

### Fases 1–9 — núcleo funcional
**STATUS: CONCLUÍDAS conforme registros anteriores; robustez/produção ainda pendentes.**

- Importação e preservação de entregas.
- Identidade segura de PhysicalStop.
- Geolocalização cadastral/fallback municipal.
- Roteamento OSRM por malha viária.
- Otimização e determinismo.
- Backend FastAPI, autenticação, licenciamento base e SQLite.
- Frontend operacional.
- Mais de 30 XLSX reais validados no PC.
- Primeiro fluxo físico Android validado pela LAN.

### Fase 10 — Robustez e produção técnica
**STATUS: EM ANDAMENTO**

- CI, regressões, carga, falhas externas, segurança e preparação de deploy.
- Testes remotos, Android de campo, backup/restauração e monitoramento permanecem pendentes.

### Fase 11 — Sistema oficial de licenças
**STATUS: EM ANDAMENTO — PERSISTÊNCIA + DISPOSITIVOS/BINDING IMPLEMENTADOS; CICLO DE VIDA E ADMINISTRAÇÃO PENDENTES**

A base existente foi preservada e evoluída para o modelo comercial. A licença continua sendo autoridade do backend e o relógio do servidor continua sendo a fonte de validade.

Milestones implementados:

- `LicenseStatus`: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`.
- `license_key` de alta entropia separado do `license_id` interno.
- plano, ativação, renovação, contador e último acesso.
- `effective_status()` dependente do servidor.
- `LicenseEvent` e histórico persistente.
- `AccountRole` (`USER`/`ADMIN`).
- Persistência/migração SQLite dos campos comerciais sem apagar dados legados.
- Unicidade de `license_key` no banco.
- Entidade `Device` e `SQLiteDeviceRepository`.
- Hash do segredo da instalação; o segredo bruto não é persistido.
- Binding de dispositivo a conta/licença.
- Enforcement server-side de `max_devices`.
- Reuso do mesmo dispositivo sem consumir novo slot.
- Revogação de dispositivo libera capacidade para nova instalação.
- Bloqueio de binding para licença expirada, suspensa ou revogada.
- Check de capacidade e inserção executados na mesma transação SQLite (`BEGIN IMMEDIATE`) para reduzir corrida entre registros concorrentes.
- Eventos de registro/reuso/limite/revogação enviados ao histórico quando o repositório de eventos está disponível.

Testes adicionados:

- `backend/tests/test_devices.py` — hash, primeiro dispositivo, limite, reuso, estados inválidos, revogação, persistência e enforcement SQLite.
- `backend/tests/test_persistence_licensing_migration.py` — migração/persistência comercial.
- `backend/tests/test_license_lifecycle_primitives.py` — estados/chave/eventos.

### Próxima subfase do licenciamento

1. Serviço transacional de geração, ativação, renovação, suspensão, reativação e revogação com regras explícitas de transição e eventos atômicos.
2. Endpoints administrativos protegidos por `AccountRole.ADMIN`.
3. Painel administrativo.
4. Histórico, filtros, dashboard e detalhes.
5. Testes adversariais, concorrência e manipulação ponta a ponta.
6. Integração do binding com o fluxo real Android → backend.
7. PIX sandbox → arquitetura de produção com provedor real/webhook autenticado.
8. Backup/restauração do licenciamento.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA**

O requisito permanece registrado em `PROJECT_MEMORY/12_UPDATE_SYSTEM.md`. Mudanças nativas Android continuam exigindo novo APK.

## Critérios para declarar o projeto pronto para uso real

- Todas as suítes automatizadas verdes.
- Nenhuma entrega válida perdida.
- Nenhum PhysicalStop válido desaparecendo.
- Localização cadastral e fallback confiáveis.
- Rota calculada por malha viária real.
- Mapa, sequência e navegação coerentes.
- Backend remoto/deploy preparado e testado.
- Licenciamento comercial completo, auditável e seguro.
- Backup/restauração validados.
- APK release assinado e instalação limpa testada.
- Segurança e escalabilidade auditadas.
- Estado do GitHub sincronizado.
- Relatório final de aceitação produzido.

## Regra de desenvolvimento

Uma alteração por vez: verificar estado → alterar → testar → analisar → revisar diff → commit → push → confirmar GitHub → somente então avançar.

Nunca declarar o projeto pronto apenas porque os testes automatizados passaram.
