# Requisito oficial — Sistema de atualização do OTIMIZER

## ID

`OTIMIZER-UPDATE-001`

## Status

**PLANEJADO — NÃO IMPLEMENTAR AINDA**

Este requisito faz parte da arquitetura futura do produto e deve permanecer no roadmap até que a base do primeiro teste físico Android esteja estabilizada.

## Objetivo

Permitir que o aplicativo Android instalado permaneça como o núcleo do cliente e receba atualizações do produto sem exigir a instalação de um novo APK para cada alteração compatível.

## Arquitetura prevista

- O APK conterá o núcleo nativo Android/WebView e o mecanismo de atualização.
- Alterações compatíveis do frontend serão distribuídas como atualizações do conteúdo da aplicação.
- O aplicativo consultará um manifesto de versão publicado pelo ambiente oficial do Otimizer.
- O manifesto informará versão, tipo de atualização e compatibilidade.
- Atualizações simples não deverão exigir reinstalação do APK.
- Alterações que afetem o código nativo Android continuarão exigindo uma nova versão do APK.

## Requisitos técnicos futuros

1. Versionamento formal de APK e conteúdo da aplicação.
2. Manifesto de atualização.
3. Diferenciação entre `PATCH` de conteúdo e `APP UPDATE` nativo.
4. Download somente por canal seguro HTTPS.
5. Verificação de integridade por hash/checksum.
6. Validação de compatibilidade antes da aplicação.
7. Proteção contra atualização parcial ou corrompida.
8. Rollback/fallback seguro quando uma atualização falhar.
9. Registro da versão efetivamente instalada.
10. Atualização automática e/ou solicitação manual conforme política futura do produto.
11. Modo de desenvolvimento que permita testar versões sem bloquear o ambiente local.
12. O aplicativo nunca deve ficar inutilizado apenas porque uma atualização falhou.

## Regra de decisão

Não implementar o sistema de atualização antes da estabilização do primeiro ciclo Android físico. Durante o desenvolvimento inicial, o APK continuará sendo gerado pelo GitHub Actions quando houver alteração nativa Android.

## Relação com patches

O GitHub continuará sendo a fonte de versionamento e CI/CD do projeto. O mecanismo futuro de atualização do aplicativo não deve depender de o entregador acessar GitHub ou instalar manualmente arquivos de desenvolvimento.

Fluxo-alvo:

`alteração → GitHub → CI/CD → publicação → manifesto → aplicativo detecta → valida → atualiza`

## Critério de conclusão futura

O requisito somente será considerado implementado quando houver pelo menos um teste real em Android comprovando uma atualização compatível sem reinstalação manual do APK, além de testes de integridade, incompatibilidade e falha/rollback.
