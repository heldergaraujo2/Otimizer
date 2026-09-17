# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado verificado em 2026-09-17

A auditoria de continuidade partiu do HEAD `081b974aca5a0855e08be565a300c1eb52442817`. Esse commit é filho de `1b94079da362a3b71652aa35d3fa6a5fd63f30db` e atualiza `PROJECT_MEMORY/12_SECURITY_AUDIT.md`. A sequência documental anterior também contém `70835fe4bfb7807b0c47bb3f925f3beb04aa6124`.

O núcleo funcional de importação, localização, PhysicalStop, OSRM, otimização, backend, frontend, licenciamento e binding Android permanece implementado. Nenhuma dessas áreas foi reestruturada nesta continuidade.

## Documentação encontrada

Existem e foram consultados `PROJECT_MEMORY/00_IDENTITY.md`, `01_PRODUCT_VISION.md`, `02_REQUIREMENTS.md`, `08_CURRENT_STATE.md`, `10_ROADMAP.md`, `11_HANDOFF.md`, `12_SECURITY_AUDIT.md` e documentos relevantes de `docs/` (`REQUIREMENTS.md`, `ARCHITECTURE.md`, `XLSX_SPEC.md`).

Os caminhos `PROJECT_MEMORY/03_ARCHITECTURE.md`, `04_ROUTING_ENGINE.md`, `05_OPTIMIZATION.md`, `06_XLSX_FORMAT.md`, `07_ROADMAP.md`, `09_DECISIONS.md` e `PROJECT_MEMORY/10_TESTS.md`, assim como `docs/ROADMAP.md` e `docs/TESTING.md`, não existem na `main` atual. Não foram recriados automaticamente, pois isso exigiria inventar histórico.

## CI — evidência atual

Os workflows existentes são Backend tests, Frontend tests, Importer tests e Android APK. No HEAD `081b974...`, o workflow `Frontend tests` executou como run `35243638706` e terminou `success`; sintaxe JavaScript e testes frontend também terminaram com sucesso.

Backend/Importer/Android não possuem execução correspondente observável para o HEAD nesta auditoria porque os gatilhos de push desses workflows usam filtros de caminho e a alteração do HEAD foi documental. Portanto, essas suítes não devem ser declaradas verdes com base neste ciclo.

A suíte local não está disponível neste ambiente porque o checkout do repositório não é montado aqui.

## Licenciamento e binding — estado implementado

- estados `GERADA`, `DISPONIVEL`, `ATIVA`, `EXPIRADA`, `SUSPENSA`, `REVOGADA`;
- chave comercial de alta entropia separada do ID interno;
- plano, ativação, renovação, contador, último acesso e entitlements;
- auditoria persistente;
- roles `USER`/`ADMIN`;
- migração SQLite e unicidade da chave;
- binding persistente, hash do segredo e enforcement server-side de `max_devices`;
- reuso do mesmo dispositivo sem consumir slot;
- revogação terminal do binding;
- Android gera segredo por instalação e o protege por Android Keystore;
- `/devices/bind` exige autenticação e licença pertencente à conta;
- resposta do binding não expõe segredo/hash;
- `/optimize` e `/optimize-manual` podem exigir `X-Otimizer-Device-ID`;
- dispositivo revogado é rejeitado server-side;
- painel administrativo gerencia licenças e dispositivos;
- transições críticas usam proteção transacional/concorrrência já existente.

## Pix

`backend/src/otimizer_api/pix_webhook.py` é apenas uma fundação provider-neutral de autenticação/validação de webhook. Não considerar Pix de produção concluído. Ainda faltam PSP real, contrato específico, endpoint real, idempotência persistente, proteção contra dupla liquidação e homologação.

## Nova etapa documental desta continuidade

Foi criado `docs/ANDROID_HOMOLOGATION.md` contendo a matriz oficial de homologação física dos cenários de instalação, login, licença, binding, otimização, revogação, `max_devices`, reinstalação, estados de licença e sessão.

Nenhum cenário da matriz foi marcado como executado pelo agente. Todos permanecem `PENDENTE — TESTE FÍSICO NECESSÁRIO` até execução real.

## Próxima etapa objetiva do usuário

Executar a matriz Android em dispositivo real. O retorno necessário é, para cada cenário:

- ID;
- PASS/FAIL;
- modelo/versão Android;
- versão do APK;
- erro/código observado, se houver;
- `device_id` somente quando necessário para correlação administrativa.

Nunca enviar senha, token de sessão ou segredo bruto do dispositivo.

## Trabalho que pode continuar sem o aparelho

Enquanto os testes físicos aguardam execução, pode-se trabalhar em backup/restore provider-neutral, testes adversariais adicionais de licenciamento/autorização e preparação de integração de pagamentos sem assumir PSP.

A próxima grande implementação comercial específica continua bloqueada pela ausência de um PSP Pix definido. Não inventar provedor, endpoint ou credencial.

## Próxima sequência após homologação Android

1. PSP Pix real;
2. adaptador e webhook real;
3. idempotência persistente e dupla liquidação;
4. pagamento → licença;
5. backup + restore real;
6. VPS/DB/OSRM/HTTPS/domínio;
7. Android pela Internet;
8. monitoramento/pilotos;
9. APK Release assinado;
10. instalação limpa/auditoria/Release Candidate.

## Regra de continuidade

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca inventar execução, resultado, commit, CI, infraestrutura ou integração externa.
