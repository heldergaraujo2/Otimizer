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

## CI verificado nesta continuidade

O HEAD auditado `081b974aca5a0855e08be565a300c1eb52442817` possui uma execução observável do workflow `Frontend tests` (run `35243638706`) concluída com `success`, incluindo validação de sintaxe JavaScript e todos os testes frontend.

Os workflows Backend, Importer e Android não executaram nesse push documental devido aos filtros de caminho configurados. Assim, não há evidência nova dessas suítes no HEAD auditado e elas não são declaradas verdes neste ciclo.

O HEAD documental posterior desta continuidade (`c030ff50c5d8ba5183e633e15e72f9c45a5742c3`) acionou novamente `Frontend tests`; a execução estava `queued` no momento da última verificação. Portanto, seu resultado ainda não é declarado.

## Limitações assumidas

- O backend ainda não possui rate limiter distribuído próprio. Rate limiting de produção deve ser aplicado no gateway/VPS, com regras específicas para login e operações administrativas, mantendo proteção de aplicação quando necessário.
- Backup/restauração ainda precisa ser implementado e comprovado com restore real.
- O APK atual é debug; release comercial assinado ainda não foi produzido.
- Homologação física completa de binding, revogação, `max_devices`, reinstalação/restore e sessão expirada ainda depende de execução em dispositivo real.
- Infraestrutura de produção (VPS, domínio, HTTPS, DB/OSRM remoto e observabilidade) ainda não está homologada.

## Homologação Android

Foi criada `docs/ANDROID_HOMOLOGATION.md` com matriz de 17 cenários. Todos permanecem pendentes de execução física até que sejam realizados em aparelho Android real.

Nenhum resultado físico é inferido a partir do código ou do workflow de build.

## Próximo objetivo

Executar a homologação física do Android sobre o binding já implementado. Em paralelo, podem ser preparados componentes provider-neutral de backup/restore e testes adicionais de segurança, sem declarar restore real nem Pix real concluídos.
