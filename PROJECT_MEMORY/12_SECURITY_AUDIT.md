# Auditoria de Segurança — Licenciamento e Autenticação

## Escopo

Revisão da camada comercial do OTIMIZER após a implementação de estados formais de licença, auditoria, binding de dispositivos, proteção contra concorrência, painel administrativo e integração do binding no cliente Android.

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

## PIX

A camada atual de webhook Pix é provider-neutral e cobre HMAC-SHA256, timestamp, janela anti-replay, comparação em tempo constante, prefixo `sha256=`, validação estrita de evento/pagamento/valor/status e testes adversariais.

Isso **não equivale a integração Pix de produção**. Falta PSP real, contrato de assinatura específico, endpoint ligado ao provedor, idempotência persistente, proteção contra dupla liquidação e homologação.

## Limitações assumidas

- O backend ainda não possui rate limiter distribuído próprio. Rate limiting de produção deve ser aplicado no gateway/VPS, com regras específicas para login e operações administrativas, mantendo proteção de aplicação quando necessário.
- Backup/restauração ainda precisa ser implementado e comprovado com restore real.
- O APK atual é debug; release comercial assinado ainda não foi produzido.
- Homologação física completa de binding, revogação, `max_devices`, reinstalação/restore e sessão expirada ainda depende de execução em dispositivo real.
- Infraestrutura de produção (VPS, domínio, HTTPS, DB/OSRM remoto e observabilidade) ainda não está homologada.

## Evidência de CI

Historicamente, o SHA `087f1cc5615b5898bc027a6ba61b8138a734c86b` teve Backend tests e Frontend tests concluídos com sucesso. Entretanto, o commit atual auditado não possui workflow run observável pela integração disponível. Portanto, não declarar a `main` atual verde sem nova evidência.

## Próximo objetivo

Executar a homologação física do Android sobre o binding já implementado. Em seguida, avançar para PSP Pix real e backup/restauração, sem inventar credenciais, resultados de testes ou infraestrutura.
