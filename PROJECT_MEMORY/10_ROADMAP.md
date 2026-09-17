# Roadmap — OTIMIZER

## Objetivo final

Transformar XLSX reais de entregas em uma rota confiável, preservando todas as entregas válidas, identificando propriedades/paradas físicas, resolvendo localização com as melhores evidências disponíveis, roteando pela malha viária real e entregando uma sequência navegável ao motorista.

Fluxo-alvo:

`XLSX → Delivery → evidências → localização da propriedade → ponto de acesso → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Estado das fases

### Fase 1 — Importação e preservação de entregas
**STATUS: CONCLUÍDA**

- Leitura dos XLSX reais.
- Preservação das entregas válidas.
- Tratamento de latitude/longitude inválidas ou `0,0` sem descartar a entrega.
- Auditoria de linhas e pendências.

### Fase 2 — Identidade de PhysicalStop
**STATUS: CONCLUÍDA**

- Latitude/longitude não são a única identidade.
- Endereço, número, quadra e lote participam quando disponíveis.
- Conflitos explícitos impedem fusões inseguras.
- `Sequence`/`Stop` da planilha não determinam identidade física.
- Entregas e PhysicalStops são contabilizados separadamente.

### Fase 3 — Geolocalização cadastral de Goiânia
**STATUS: IMPLEMENTAÇÃO PRINCIPAL CONCLUÍDA; VALIDAÇÃO CONTÍNUA**

- Provider específico de Goiânia.
- Integração com camadas oficiais de lotes, quadras, número predial e segmentos de logradouro.
- Quando há `bairro + quadra + lote`, o lote cadastral passa a ser a evidência prioritária para identidade da propriedade, mesmo quando existe GPS na planilha.
- O ponto da propriedade e o ponto de acesso viário são mantidos conceitualmente separados.
- A resolução pode permanecer pendente quando não houver evidência suficiente.
- O caso real sem GPS `Rua SR 2 / quadra 30 / lote 24` foi incorporado aos testes sintéticos.

### Fase 4 — Roteamento por malha viária
**STATUS: CONCLUÍDA NA ARQUITETURA ATUAL**

- Provider OSRM.
- Matriz de custos de estrada.
- Distância e duração.
- Origem e destino opcionais.
- Retorno ao início.
- Tratamento de trechos inacessíveis.
- Métricas calculadas a partir da mesma matriz usada pela otimização.

### Fase 5 — Otimização da sequência
**STATUS: CONCLUÍDA NA IMPLEMENTAÇÃO ATUAL**

- Objetivo por tempo ou distância.
- Solver exato para rotas pequenas.
- Estratégias heurísticas para rotas maiores.
- Multi-start quando existe origem livre.
- Regret insertion.
- Greedy como fallback.
- 2-opt com preservação de endpoints e restrições de retorno.
- Comparação determinística com critério secundário.
- Validação de cobertura para impedir desaparecimento de PhysicalStops.

### Fase 6 — Backend e contrato da aplicação
**STATUS: CONCLUÍDA NA BASE ATUAL**

- FastAPI.
- Autenticação/sessões.
- Licenciamento.
- Persistência SQLite.
- Endpoint de otimização.
- Tratamento dos principais erros de entrada/roteamento.
- CORS compatível com o shell Android de teste.

### Fase 7 — Frontend operacional
**STATUS: CONCLUÍDA NA BASE ATUAL**

- Upload XLSX.
- Seleção do objetivo.
- Origem/destino/retorno ao início.
- Mapa Leaflet.
- Marcadores numerados.
- Lista e detalhes das paradas.
- Navegação para a próxima parada.
- Estado visual de parada visitada.
- Fluxo de login.
- Rota manual e reotimização.

### Fase 8 — Validação real no PC
**STATUS: CONCLUÍDA PARA O FLUXO FUNCIONAL PRINCIPAL**

Validações realizadas:

- Ambiente Python/venv.
- Suite automatizada do projeto.
- Backend iniciando.
- Frontend iniciando.
- **Mais de 30 XLSX reais** processados no PC.
- Caso com localização incompleta/pendente.
- Conservação das entregas.
- PhysicalStops coerentes.
- Otimização e reotimização.
- Mapa, marcadores e detalhes.
- Autocomplete municipal e alfinete de rua.
- Rota manual.

O usuário informou que o fluxo foi **100% funcional conforme esperado** nos testes realizados no PC. Permanecem validações de robustez e produção fora do escopo dessa conclusão.

### Fase 9 — Primeiro teste físico Android
**STATUS: CONCLUÍDA — PRIMEIRO FLUXO OPERACIONAL APROVADO**

Validação realizada pelo usuário em 17/09/2026:

- APK instalado no Android.
- Login funcionando.
- Novo XLSX importado pelo aplicativo.
- Otimização automática funcionando.
- Rota/paradas manuais funcionando.
- Reotimização após alteração manual funcionando.
- Comunicação do aparelho com backend local pela rede LAN funcionando.

Correções que viabilizaram o teste:

- WebView configurado para permitir mixed content no cenário de backend HTTP LAN de desenvolvimento.
- Origem `https://appassets.androidplatform.net` adicionada ao CORS padrão do backend.
- Teste automatizado da origem Android adicionado.
- Workflow de geração do APK validado anteriormente com sucesso.

**Limite desta fase:** isso comprova o fluxo operacional inicial em aparelho físico, mas não representa aprovação para produção. Ainda faltam backend remoto, segurança de produção, assinatura/release, testes de rede instável, permissões/retomada, cargas maiores e distribuição.

## Próximas evoluções técnicas

### Prioridade A — Robustez de localização
- Validar mais casos reais de `quadra + lote` no campo.
- Medir diferença entre GPS original, ponto cadastral da propriedade e ponto de acesso viário.
- Melhorar seleção do ponto de acesso considerando a face do lote/logradouro quando os dados oficiais permitirem.
- Adicionar mais casos de endereço incompleto e conflitos de evidência.
- Criar cache/index local das geometrias quando a carga real justificar.

### Prioridade B — Estabilização técnica e CI
- Confirmar execução verde dos quatro workflows ativos no estado atual: Android APK, Backend, Frontend e Importer.
- Manter testes automatizados verdes a cada alteração.
- Resolver qualquer divergência entre ambiente local e CI.
- Fazer teste de carga com planilhas maiores.
- Medir tempo de resolução cadastral e matriz OSRM.
- Revisar dependências e warnings conhecidos.
- Auditar múltiplas pernas não roteáveis e falhas de serviços externos.
- Auditar repetibilidade/determinismo em cenários adicionais.

### Prioridade C — Android de campo e produção
- Testar perda/retomada de conexão.
- Testar comportamento quando o backend estiver remoto, e não no PC.
- Validar configuração de ambiente sem IP LAN fixo.
- Revisar permissões Android e ciclo de vida do aplicativo.
- Testar importação de arquivos maiores no aparelho.
- Testar rotas longas e múltiplas reotimizações.
- Preparar assinatura de release e pacote de distribuição.
- Definir estratégia segura de armazenamento de configuração e credenciais.

### Prioridade D — Intervenção manual do motorista
**PLANEJADA — NÃO IMPLEMENTAR AINDA**

- Selecionar uma parada.
- Escolher/reinserir sua posição na sequência.
- Transformar a escolha em restrição real da otimização.
- Recalcular a rota.
- Reotimizar as demais paradas ao redor da decisão manual.
- Atualizar sequência, mapa, métricas e navegação.
- Permitir novas intervenções segundo regras que serão definidas antes da implementação.

Observação: a capacidade atual de **adicionar uma parada manual e reotimizar** já foi validada; esta prioridade se refere ao controle avançado da posição/ordem de uma parada existente.

### Prioridade E — Sistema oficial de atualização por patch
**PLANEJADO — NÃO IMPLEMENTAR AINDA**

Requisito registrado em `PROJECT_MEMORY/12_UPDATE_SYSTEM.md`.

Objetivo:

- alterações compatíveis de frontend/conteúdo devem poder chegar ao aplicativo por patch sem exigir novo APK;
- alterações nativas Android continuam exigindo novo APK;
- futuro Update Manager deverá trabalhar com versão, compatibilidade, checksum, integridade, rollback e fallback seguro;
- o APK continua sendo a base nativa do aplicativo.

### Prioridade F — Produto comercial
Depois da estabilidade técnica:

- Pagamentos Pix em produção.
- Regras de licença/limites.
- Auditoria.
- Observabilidade.
- Segurança de produção.
- Deploy.
- UX comercial.

## Critérios para declarar o projeto pronto para uso real

- Todas as suítes automatizadas verdes.
- Nenhuma entrega válida perdida.
- Nenhum PhysicalStop válido desaparecendo da rota.
- Localização cadastral funcionando quando houver evidência suficiente.
- Entregas sem GPS não são descartadas.
- Quando o ponto exato não puder ser cravado, a rua correta é usada como fallback sempre que puder ser determinada com confiança suficiente.
- Pontos de propriedade, acesso exato e fallback de rua tratados corretamente e identificados por nível de confiança.
- Rota calculada por malha viária real.
- Mapa, sequência e navegação coerentes.
- Mais de 30 XLSX reais validados no PC.
- Primeiro fluxo operacional Android validado em aparelho físico.
- Caso sem GPS válido validado no PC.
- Falhas de serviços externos diferenciadas de falhas do código.
- Backend remoto/deploy preparado e testado.
- APK de release assinado e processo de distribuição definido.
- Estado do GitHub sincronizado.
- Relatório final de aceitação produzido.

## Regra de desenvolvimento

Uma alteração por vez: verificar estado → alterar → testar → analisar → revisar diff → commit → push → confirmar GitHub → somente então avançar.

Nunca declarar o projeto pronto apenas porque os testes automatizados passaram.
