# Auditoria de Segurança — Licenciamento, Autenticação e Recuperação

## Escopo

Revisão da camada comercial do OTIMIZER após estados formais de licença, auditoria, binding de dispositivos, proteção contra concorrência, painel administrativo, integração do binding no Android e início da camada de recuperação de dados.

## Controles confirmados no estado atual

- Senhas são protegidas com Argon2id e exigem pelo menos 12 caracteres.
- Tokens de sessão são aleatórios e somente o hash SHA-256 é persistido no servidor.
- Sessões têm expiração server-side e podem ser revogadas.
- Vida padrão da sessão: 12 horas.
- A validade de licença usa o relógio do servidor.
- Licenças possuem estados formais e revogação é terminal.
- Chaves comerciais são aleatórias e independentes do ID interno.
- Chave comercial possui unicidade no banco.
- Alterações de licença e seus eventos de auditoria podem ser persistidos na mesma transação SQLite.
- Transições concorrentes rejeitam estado obsoleto para evitar lost update.
- Limite de dispositivos é imposto server-side dentro de transação SQLite.
- Segredo de instalação não é persistido em claro no backend; somente hash SHA-256 é armazenado.
- Endpoints administrativos exigem sessão válida e role ADMIN.
- Respostas administrativas não expõem o hash do segredo de dispositivo.
- Usuários comuns não podem consultar ou alterar recursos administrativos.
- Android gera segredo por instalação e o protege com Android Keystore; o backend recebe a prova necessária para binding e não armazena o segredo bruto.
- `/optimize` e `/optimize-manual` podem exigir `X-Otimizer-Device-ID` quando o repositório de dispositivos está ativo.
- Dispositivo revogado é rejeitado server-side mesmo com licença ativa.

## Backup/restore — nova camada de segurança

`backend/src/otimizer_api/backup.py` adiciona uma fundação provider-neutral para SQLite:

- snapshot com `sqlite3.Connection.backup()`;
- publicação atômica com arquivo temporário + replace;
- manifest versionado;
- SHA-256 do artefato;
- `PRAGMA integrity_check` antes de aceitar o backup;
- presença das tabelas críticas `accounts`, `sessions`, `licenses`, `license_events` e `payments`;
- conferência de contagem dos registros contra o manifest;
- permissões locais `0600` para backup e manifest;
- restore validado em arquivo temporário antes de substituir o destino;
- falha de integridade ou adulteração não substitui um destino existente.

`backend/tests/test_backup.py` cobre round-trip e cenários adversariais básicos de integridade.

**Risco residual:** o snapshot contém dados operacionais sensíveis, portanto o arquivo precisa de proteção de armazenamento/criptografia adequada no ambiente de produção. Retenção, destino externo/imutável, agendamento, alertas e restore operacional ainda não foram homologados.

**Sessões:** o backup preserva a tabela `sessions` porque ela faz parte do estado persistente atual. O procedimento de produção deve definir explicitamente invalidação/reautenticação após restauração; não considerar que restaurar sessões antigas seja automaticamente seguro.

## PIX

A camada atual de webhook Pix é provider-neutral e cobre HMAC-SHA256, timestamp, janela anti-replay, comparação em tempo constante, prefixo `sha256=`, validação estrita de evento/pagamento/valor/status e testes adversariais.

Isso **não equivale a integração Pix de produção**. Falta PSP real, contrato de assinatura específico, endpoint ligado ao provedor, idempotência persistente, proteção contra dupla liquidação e homologação.

## CI verificado nesta continuidade

O checkout não está disponível localmente no ambiente do agente. Para o commit de implementação/testes `4a5edf725ecbdc458aaf5e7b0d0d16ee002b0380`, não houve execução de workflow observável pelo conector e o combined status retornou vazio. Portanto, nenhum resultado de CI Backend é declarado verde nesta etapa.

## Homologação Android

`docs/ANDROID_HOMOLOGATION.md` contém a matriz de 17 cenários. Todos permanecem pendentes de execução física até realização em aparelho Android real.

Nenhum resultado físico é inferido a partir do código ou do workflow de build.

## Limitações atuais

- Backup/restore operacional de produção ainda não comprovado.
- Destino externo/imutável, retenção e criptografia de backups ainda não homologados.
- Rate limiting distribuído de produção ainda depende da infraestrutura/gateway.
- APK comercial Release assinado ainda não foi produzido/homologado.
- VPS, domínio, HTTPS, DB/OSRM remoto e observabilidade ainda não estão homologados.
- PSP Pix real ainda não definido.

## Próximo objetivo

Completar o runbook e a prova automatizada de recuperação em ambiente controlado, depois executar restore real em infraestrutura apropriada. Em paralelo, concluir a homologação física Android. Não declarar recuperação de produção nem Pix de produção concluídos sem evidência correspondente.
