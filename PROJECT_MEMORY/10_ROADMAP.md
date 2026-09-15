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

### Fase 8 — Validação real no PC
**STATUS: PRÓXIMA FASE PRINCIPAL**

Validar no computador do usuário, sem alterar os XLSX:

1. Ambiente Python/venv.
2. Suite importer.
3. Suite backend.
4. Backend iniciando.
5. Frontend iniciando.
6. Primeiro XLSX real.
7. Segundo XLSX real.
8. Terceiro XLSX real.
9. Caso sem GPS válido.
10. Conservação de 100% das entregas.
11. PhysicalStops coerentes.
12. Rota completa.
13. Mapa e marcadores.
14. Detalhes.
15. Navegação.
16. Repetibilidade.

## Próximas evoluções técnicas

### Prioridade A — Fechar validação de localização
- Validar o caso real de `quadra + lote` no PC.
- Medir a diferença entre GPS original, ponto cadastral da propriedade e ponto de acesso viário.
- Melhorar seleção do ponto de acesso considerando a face do lote/logradouro quando os dados oficiais permitirem.
- Adicionar mais casos de endereço incompleto e conflitos de evidência.
- Criar cache/index local das geometrias quando a carga real justificar.

### Prioridade B — Estabilizar produção
- Confirmar todos os workflows do GitHub Actions verdes.
- Resolver qualquer divergência entre ambiente local e CI.
- Fazer teste de carga com planilhas maiores.
- Medir tempo de resolução cadastral e matriz OSRM.
- Revisar dependências e warnings conhecidos.

### Prioridade C — Intervenção manual do motorista
**PLANEJADA — NÃO IMPLEMENTAR AINDA**

- Selecionar uma parada.
- Escolher/reinserir sua posição na sequência.
- Transformar a escolha em restrição real da otimização.
- Recalcular a rota.
- Reotimizar as demais paradas ao redor da decisão manual.
- Atualizar sequência, mapa, métricas e navegação.
- Permitir novas intervenções segundo regras que serão definidas antes da implementação.

### Prioridade D — Produto comercial
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
- Pontos de propriedade e acesso viário tratados corretamente.
- Rota calculada por malha viária real.
- Mapa, sequência e navegação coerentes.
- Três XLSX reais validados no PC.
- Caso sem GPS válido validado no PC.
- Falhas de serviços externos diferenciadas de falhas do código.
- Estado do GitHub sincronizado.
- Relatório final de aceitação produzido.

## Regra de desenvolvimento

Uma alteração por vez: verificar estado → alterar → testar → analisar → revisar diff → commit → push → confirmar GitHub → somente então avançar.

Nunca declarar o projeto pronto apenas porque os testes automatizados passaram.
