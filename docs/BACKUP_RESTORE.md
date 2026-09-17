# Backup e restauração — OTIMIZER

## Objetivo

Definir o procedimento operacional para proteger e recuperar o estado persistente do backend sem depender de um PSP ou fornecedor específico.

## Escopo dos dados

O banco SQLite atual contém, no mínimo, as tabelas críticas:

- `accounts`
- `sessions`
- `licenses`
- `license_events`
- `payments`

O utilitário `backend/src/otimizer_api/backup.py` valida explicitamente essas tabelas.

## Artefatos

Para um backup `otimizer-YYYYMMDD-HHMMSS.db`, o processo cria também o manifest `otimizer-YYYYMMDD-HHMMSS.db.json`.

O manifest registra:

- versão do formato;
- timestamp UTC de criação;
- SHA-256 do banco;
- tamanho do arquivo;
- contagem por tabela crítica.

Os arquivos são publicados atomicamente e recebem permissão local `0600` quando o sistema operacional suporta essa permissão.

## Criação

Use `create_backup(database_path, backup_path)` a partir do ambiente Python do backend.

Exemplo conceitual:

```python
from otimizer_api.backup import create_backup

create_backup(
    "/caminho/otimizer.db",
    "/caminho/seguro/backups/otimizer-20260917-120000.db",
)
```

O backup falha se o banco de origem não existir, se o destino for o próprio banco, ou se o snapshot não passar na validação SQLite.

## Validação

Antes de considerar um arquivo utilizável:

```python
from otimizer_api.backup import validate_backup

validate_backup("/caminho/seguro/backups/otimizer-20260917-120000.db")
```

A validação confere manifest, SHA-256, `PRAGMA integrity_check`, tabelas críticas e contadores registrados.

## Retenção

A política deve ser configurada pelo ambiente operacional. O utilitário fornece `prune_backups(directory, keep=N)`.

Somente backups válidos além da quantidade de retenção são removidos. Arquivos inválidos são preservados para investigação. O manifest correspondente só é removido depois do banco.

A política inicial sugerida para homologação é manter pelo menos 7 snapshots válidos, mas o valor definitivo de produção deve considerar RPO/RTO, volume e armazenamento disponível.

## Restauração controlada

Nunca sobrescreva diretamente o banco de produção como primeira ação. Primeiro restaure para um caminho separado:

```python
from otimizer_api.backup import restore_backup

restore_backup(
    "/caminho/seguro/backups/otimizer-20260917-120000.db",
    "/caminho/staging/otimizer-restored.db",
)
```

A rotina valida o backup antes de copiar, valida o banco restaurado e só então publica o arquivo-alvo atomicamente.

## Pós-restore obrigatório

1. Parar/isol ar a instância que utilizará o banco restaurado.
2. Confirmar que o snapshot foi validado.
3. Restaurar primeiro em ambiente controlado.
4. Iniciar o backend apontando para o banco restaurado.
5. Verificar contas, licenças, eventos, pagamentos e dispositivos relacionados.
6. Executar testes funcionais mínimos, incluindo autenticação e autorização.
7. Tratar sessões restauradas explicitamente: a política de produção deve invalidar sessões potencialmente antigas e exigir nova autenticação quando necessário.
8. Somente depois considerar a substituição do banco operacional.
9. Registrar data, snapshot, operador e resultado do exercício de recuperação sem registrar senhas, tokens ou segredos de dispositivo.

## Segurança do armazenamento

O snapshot contém dados sensíveis. O repositório fornece proteção de integridade, mas não substitui controles de armazenamento de produção. O destino final deve aplicar acesso mínimo, criptografia em repouso quando apropriada, proteção contra exclusão acidental e, para produção, uma cópia externa/imutável adequada ao modelo de ameaça.

Não armazenar backups de produção dentro do repositório Git.

## RPO/RTO e monitoramento

Antes do lançamento comercial devem ser definidos:

- RPO (quanto de dados pode ser perdido);
- RTO (tempo máximo aceitável para recuperação);
- frequência do backup;
- retenção diária/semanal/mensal;
- destino primário e secundário;
- alertas de falha;
- exercício periódico de restore.

## Estado atual

**IMPLEMENTAÇÃO TÉCNICA:** presente.

**BACKUP OPERACIONAL DE PRODUÇÃO:** pendente.

**RESTORE REAL HOMOLOGADO:** pendente.

**ARMAZENAMENTO EXTERNO/IMUTÁVEL:** pendente.

**CRIPTOGRAFIA/SEGREDOS DE PRODUÇÃO:** pendente de definição da infraestrutura real.

O componente e seus testes automatizados não constituem prova de recuperação de produção.
