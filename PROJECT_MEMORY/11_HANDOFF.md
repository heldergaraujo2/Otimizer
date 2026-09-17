# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Estado verificado em 2026-09-17

A continuidade anterior fechou a auditoria do núcleo e a matriz de homologação Android. O HEAD anterior era `b346edc61c49dbf02d8dbae464d064e9e3c83239`.

Nesta etapa, a próxima frente independente foi executada sem recomeçar o projeto: fundação provider-neutral de backup/restore sobre a persistência SQLite existente.

## Persistência atual relevante

`backend/src/otimizer_api/persistence.py` usa SQLite e mantém as entidades operacionais críticas em `accounts`, `sessions`, `licenses`, `license_events` e `payments`. O desenho existente de transações/licenciamento foi preservado.

## Backup/restore implementado nesta etapa

Arquivo: `backend/src/otimizer_api/backup.py`

Controles implementados:

- snapshot usando `sqlite3.Connection.backup()`;
- arquivo temporário no mesmo diretório e `os.replace()` para publicação atômica;
- manifest JSON versionado (`format_version=1`);
- SHA-256 do snapshot;
- `PRAGMA integrity_check`;
- presença obrigatória das tabelas críticas;
- contagem de registros das tabelas críticas gravada e conferida no manifest;
- permissões `0600` nos artefatos criados;
- restore para caminho separado, com validação completa antes de substituir o alvo;
- alvo existente permanece intacto quando a validação falha;
- nenhuma rotina registra ou retorna segredo bruto de dispositivo, senha ou token.

Testes: `backend/tests/test_backup.py` cobre round-trip, integridade, adulteração do arquivo, manifest ausente, não substituição de alvo inválido e prevenção de backup sobre a própria origem.

Commits desta etapa:

- `719039bb48b54680bb9ad76b086ee2d441ab938c` — implementação;
- `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380` — testes;
- `6d8e5a98866623b9ba346efba0162e6760b23c8c` — atualização do roadmap.

O HEAD atual é o commit `6d8e5a98866623b9ba346efba0162e6760b23c8c`.

## Limites: não considerar produção concluída

Ainda falta:

- política de retenção;
- destino externo/imutável apropriado para produção;
- criptografia em repouso conforme o ambiente de produção;
- agendamento operacional;
- monitoramento/alerta de falhas;
- procedimento de restauração documentado para o serviço real;
- execução de restore real e prova de recuperação da aplicação;
- decisão e implementação explícita de invalidação/reautenticação de sessões após restore;
- teste em infraestrutura de produção/staging real.

A existência de `backup.py` e de testes automatizados não equivale a backup/restore operacional de produção.

## CI desta etapa

O checkout não está montado no ambiente do agente, então os testes não foram executados localmente. Para `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380`, `fetch_commit_workflow_runs` não retornou execuções e o combined status retornou vazio. Não declarar Backend verde sem evidência posterior.

## Android

`docs/ANDROID_HOMOLOGATION.md` continua sendo a matriz oficial de 17 cenários. Todos os cenários físicos continuam pendentes até execução em aparelho real. Não inferir PASS a partir do código ou do build.

## Pix

`pix_webhook.py` continua somente provider-neutral. PSP real, contrato específico, endpoint real, idempotência persistente, dupla liquidação e homologação continuam pendentes. Não inventar provedor ou credencial.

## Próximo trabalho autônomo recomendado

1. Completar a camada operacional de backup sem inventar infraestrutura: retenção configurável, validação de destino e documentação do runbook.
2. Criar prova automatizada de restore + boot da aplicação usando banco restaurado, sem chamar isso de restore de produção.
3. Reforçar testes adversariais de autenticação/licenciamento se houver lacunas identificadas no código atual.
4. Em paralelo, aguardar os resultados físicos da matriz Android.
5. Somente após definição de PSP real implementar a integração Pix específica.

## Regra de continuidade

`VERIFICAR → ALTERAR → TESTAR → REVISAR → COMMIT → PUSH → DOCUMENTAR → PRÓXIMA ETAPA`.

Nunca inventar execução, resultado, commit, CI, infraestrutura ou integração externa.
