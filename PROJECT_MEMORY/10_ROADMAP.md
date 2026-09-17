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
**STATUS: EM ANDAMENTO — NÚCLEO COMERCIAL INICIAL IMPLEMENTADO; ADMINISTRAÇÃO E INTEGRAÇÃO AINDA PENDENTES**

Auditoria realizada antes da alteração:

- O projeto já possuía `License`, `Entitlements`, autenticação/sessões, SQLite, autorização server-side, `/licenses/me` e PIX sandbox.
- Não possuía máquina de estados comercial completa, chave comercial separada, histórico de eventos, RBAC administrativo, dispositivos/binding, painel administrativo ou auditoria comercial completa.

Milestone implementado no GitHub:

- `LicenseStatus` formalizado: `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`.
- `license_id` permanece identificador interno e `license_key` passa a representar a credencial comercial de alta entropia.
- `License` ganhou campos de plano, ativação, renovação e último acesso, preservando compatibilidade dos construtores existentes.
- `Entitlements` passou a validar limites positivos.
- `LicenseEvent` e repositório em memória foram adicionados como base de histórico imutável.
- `AccountRole` (`USER`/`ADMIN`) foi introduzido como fundação para RBAC administrativo.
- Testes unitários novos cobrem geração de chave, estados, expiração por hora do servidor, suspensão, revogação e limites.

Commits do milestone:

- `3058a0fd50d70901d82cd02e82900673db944856` — núcleo do ciclo comercial.
- `6b1a2f4c6db0fc15904c4835bbce234dbbbcdeab` — roles de conta.
- `0f2fe7331f91015068f04269517b443f8e3f6ad8` — testes do núcleo.

### Próxima subfase do licenciamento

1. Persistir os novos campos de licença/role sem quebrar bancos existentes.
2. Criar dispositivos e enforcement de `max_devices`.
3. Implementar serviço transacional de geração, ativação, renovação, suspensão, reativação e revogação com eventos de auditoria.
4. Expor endpoints administrativos protegidos por role.
5. Construir painel administrativo.
6. Integrar histórico, filtros, dashboard e auditoria.
7. Ampliar testes adversariais, concorrência e manipulação.
8. Evoluir PIX sandbox para arquitetura de produção com provedor real/webhook autenticado.
9. Validar backup/restauração do licenciamento.

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
