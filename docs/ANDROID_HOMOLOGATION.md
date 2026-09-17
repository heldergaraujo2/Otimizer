# Homologação Android — Device Binding e Licenciamento

## Objetivo

Validar em dispositivo Android real o fluxo comercial já implementado no backend e no cliente WebView, sem considerar inspeção de código como substituto de teste físico.

## Estado da engenharia

O binding já está implementado. O Android gera um segredo por instalação, protege-o com Android Keystore e conclui o binding antes de liberar a otimização. O backend usa `X-Otimizer-Device-ID` e aplica a autorização server-side.

Este documento é uma matriz de execução. Nenhum cenário abaixo deve ser marcado como PASS sem evidência do teste realizado.

## Pré-condições

- APK debug construído pelo workflow existente ou build local verificável.
- Backend acessível pelo endereço configurado no APK.
- Conta de teste com licença válida.
- Acesso administrativo para consultar/revogar dispositivos.
- Para `max_devices`, conhecer o valor efetivo da licença de teste.
- Não utilizar segredos reais em capturas de tela, logs ou relatórios.

## Matriz

| ID | Cenário | Ação | Resultado esperado | Estado |
|---|---|---|---|---|
| AND-01 | Instalação | Instalar APK em aparelho limpo | App abre sem erro fatal | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-02 | Login | Autenticar conta de teste | Sessão aceita pelo backend | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-03 | Licença ativa | Acessar conta com licença válida | Licença reconhecida pelo servidor | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-04 | Binding inicial | Concluir primeiro binding | `device_id` criado/confirmado; segredo não exibido | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-05 | Otimização autorizada | Executar otimização após binding | Requisição aceita e usa `X-Otimizer-Device-ID` | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-06 | Revogação | ADMIN revoga o dispositivo | Binding passa a estado revogado | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-07 | Bloqueio pós-revogação | Tentar otimizar no mesmo aparelho | Backend rejeita a operação | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-08 | Segundo dispositivo | Instalar em outro aparelho e fazer binding | Segundo binding respeita a licença | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-09 | `max_devices` | Tentar exceder o limite | Novo binding é recusado server-side | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-10 | Reuso | Repetir binding do mesmo dispositivo autorizado | Não consome slot adicional | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-11 | Reinstalação | Desinstalar/reinstalar e autenticar | Comportamento do novo segredo/binding corresponde à política implementada | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-12 | Licença expirada | Usar conta com licença expirada | Operação protegida é bloqueada | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-13 | Licença suspensa | Usar conta com licença suspensa | Operação protegida é bloqueada | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-14 | Licença revogada | Usar conta com licença revogada | Operação protegida é bloqueada | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-15 | Sessão expirada | Aguardar/forçar expiração da sessão | Backend rejeita a sessão; app exige autenticação novamente | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-16 | Novo login | Autenticar novamente após expiração | Nova sessão é aceita se licença/binding forem válidos | PENDENTE — TESTE FÍSICO NECESSÁRIO |
| AND-17 | Revalidação | Após novo login, executar otimização | Backend revalida conta + licença + dispositivo | PENDENTE — TESTE FÍSICO NECESSÁRIO |

## Evidência mínima por cenário

Registrar somente:

- ID do cenário;
- PASS/FAIL;
- data/hora aproximada;
- aparelho Android/modelo e versão;
- versão do APK;
- mensagem/código de erro observado, quando houver;
- `device_id` somente se necessário para correlação administrativa.

Nunca registrar o segredo bruto do dispositivo, tokens de sessão, senha, credenciais administrativas ou credenciais de PSP.

## Critério de conclusão

A homologação Android somente pode ser considerada concluída quando todos os cenários aplicáveis tiverem resultado físico registrado e as falhas tiverem sido corrigidas e retestadas.

Um workflow de build verde não substitui esses testes.

## Dependências externas

Os testes físicos dependem de um aparelho Android e de um backend acessível. A execução desses cenários não pode ser simulada pelo agente como se tivesse ocorrido em hardware real.
