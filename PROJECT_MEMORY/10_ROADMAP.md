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
**STATUS: EM ANDAMENTO — PERSISTÊNCIA COMERCIAL COMPATÍVEL CONCLUÍDA; SERVIÇO/ADMIN/DISPOSITIVOS AINDA PENDENTES**

Auditoria realizada antes da alteração:

- O projeto já possuía `License`, `Entitlements`, autenticação/sessões, SQLite, autorização server-side, `/licenses/me` e PIX sandbox.
- Não possuía máquina de estados comercial completa, chave comercial separada, histórico de eventos, RBAC administrativo, dispositivos/binding, painel administrativo ou auditoria comercial completa.

Milestones implementados no GitHub:

- `LicenseStatus` formalizado: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`.
- `license_id` permanece identificador interno e `license_key` representa a credencial comercial de alta entropia.
- `License` possui plano, ativação, renovação e último acesso, preservando compatibilidade dos construtores existentes.
- `Entitlements` valida limites positivos.
- `LicenseEvent` fornece base de histórico imutável.
- `AccountRole` (`USER`/`ADMIN`) fornece fundação para RBAC administrativo.
- SQLite agora persiste role, chave, estado, plano, ativação, renovação e último acesso.
- Foi criada tabela persistente `license_events` com índice temporal por licença.
- Foi criada unicidade de banco para `license_key`.
- Migração é aditiva: bancos legados recebem colunas ausentes e chaves retrocompatíveis antes do índice único, sem apagar dados existentes.
- Liquidação PIX sandbox continua vinculada à licença e agora atualiza estado/renovação persistidos.
- Testes adicionados para role, campos comerciais, unicidade, histórico durável e migração de banco legado.

Commits do núcleo comercial e persistência:

- `3058a0fd50d70901d82cd02e82900673db944856` — núcleo do ciclo comercial.
- `6b1a2f4c6db0fc15904c4835bbce234dbbbcdeab` — roles de conta.
- `0f2fe7331f91015068f04269517b443f8e3f6ad8` — testes do núcleo.
- `671c2592cef433422584296756c0e5b604ae000f` — documentação do milestone inicial.
- `c7b538b0efdd95f6b6bc931fc7aef44c7db3a438` — handoff do milestone inicial.
- `a351e8eb343293a40c6a00d2c3999eff8bd6b14c` — persistência comercial/migração.
- `9cbf64e30ceb3fc0afb44fe1fe5763c14458a138` — testes de migração/persistência.

### Próxima subfase do licenciamento

1. **Próxima etapa imediata:** dispositivos, vínculo de licença e enforcement real de `max_devices`.
2. Serviço transacional de geração, ativação, renovação, suspensão, reativação e revogação com eventos de auditoria.
3. Endpoints administrativos protegidos por `AccountRole.ADMIN`.
4. Painel administrativo.
5. Histórico, filtros, dashboard e auditoria operacional.
6. Testes adversariais, concorrência e manipulação.
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
