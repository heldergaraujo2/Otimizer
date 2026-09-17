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
**EM ANDAMENTO — núcleo, persistência, dispositivos e serviço de ciclo de vida implementados; API administrativa/painel ainda pendentes.**

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
- serviço transacional de domínio para ativação, renovação, suspensão, reativação, revogação e expiração;
- transições inválidas bloqueadas;
- revogação permanente;
- expiração baseada no relógio do servidor;
- auditoria de cada transição;
- testes do ciclo de vida.

### Próxima subfase do licenciamento

1. Endpoints administrativos protegidos por `AccountRole.ADMIN`.
2. Operações de geração, consulta, ativação, renovação, suspensão, reativação, revogação e dispositivos via API.
3. Dashboard, listagem, detalhes e histórico administrativo.
4. Segurança adversarial dos endpoints e testes de abuso/concorrência.
5. Integração Android do binding com o fluxo real de login/licença.
6. PIX de produção com provedor e webhook autenticado.
7. Backup/restauração do licenciamento.

### Sistema de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA.**

## Critérios de release

Todas as suítes verdes, preservação integral das entregas/PhysicalStops, localização e roteamento confiáveis, backend remoto testado, licenciamento comercial auditável, backup/restore, APK release assinado, instalação limpa, segurança e escalabilidade auditadas.

## Regra

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca declarar pronto somente porque testes automatizados passaram.
