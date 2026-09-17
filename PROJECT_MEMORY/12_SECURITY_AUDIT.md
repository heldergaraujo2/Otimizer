# Auditoria de Segurança — Licenciamento e Autenticação

## Escopo

Revisão da camada comercial do OTIMIZER após a implementação de estados formais de licença, auditoria, binding de dispositivos, proteção contra concorrência e painel administrativo.

## Controles confirmados

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

## Limitações assumidas

- O backend ainda não possui um rate limiter distribuído próprio. Não será tratado um contador em memória como solução de produção para múltiplas instâncias.
- Rate limiting de produção deve ser aplicado no gateway/VPS, com regras específicas para login e operações administrativas, preservando também proteção no nível da aplicação quando necessário.
- O PIX atual permanece sandbox até integração com provedor real e webhook autenticado.
- O Android ainda não está vinculado ao backend pelo segredo de instalação no fluxo final; essa é a próxima implementação obrigatória.

## Evidência de CI

O SHA `087f1cc5615b5898bc027a6ba61b8138a734c86b` teve o workflow Backend tests concluído com sucesso após a correção do fixture adversarial. O workflow Frontend tests correspondente também concluiu com sucesso.

## Próximo objetivo

Implementar o binding de dispositivo no Android usando Android Keystore, enviar a prova de instalação ao backend e exigir esse vínculo nas operações protegidas. O objetivo é que uma conta com licença ativa não seja suficiente, isoladamente, para autorizar o uso de uma instalação não vinculada.
