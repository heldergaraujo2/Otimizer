# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch principal `main`.

## Objetivo do produto

Transformar planilhas XLSX de entregas em uma rota real otimizada por rede viária, preservando 100% das entregas válidas:

XLSX -> importação -> validação -> Delivery -> PhysicalStop -> matriz rodoviária -> otimização -> sequência -> mapa -> detalhes -> navegação.

## Regras de domínio que NÃO podem ser quebradas

- Toda linha com latitude e longitude válidas é uma Delivery e deve ser preservada exatamente uma vez.
- `Sequence` e `Stop` da planilha são informativos; nunca usar esses campos para decidir inclusão ou ordem final.
- Delivery nunca é mesclada nessa camada.
- PhysicalStop representa uma localização física e pode conter várias Deliveries.
- Coordenadas iguais podem ser agrupadas em um PhysicalStop; coordenadas diferentes permanecem separadas.
- Todo PhysicalStop roteado recebe exatamente uma sequência contígua começando em 1.
- Nenhum PhysicalStop válido pode desaparecer da rota.
- Entregas válidas e paradas físicas precisam ser contabilizadas separadamente.
- Custos de rota devem vir da rede viária, não de distância em linha reta.

## Dados reais já validados

Os três XLSX de referência foram lidos no ambiente de execução. São 293 linhas válidas no total, todas com latitude/longitude numéricas.

- Caso 125 entregas: 61 PhysicalStops por coordenada; maior agrupamento = 37 entregas.
- Caso 37 entregas: 35 PhysicalStops; 14 linhas sem Sequence/Stop.
- Caso 131 entregas: 90 PhysicalStops; maior agrupamento = 8 entregas.
- Há duplicidades reais de coordenadas nos três casos.

Detalhes agregados e seguros estão em `PROJECT_MEMORY/12_REAL_XLSX_VALIDATION.md`.

## Arquitetura atual

### Importer

`importer/src/otimizer_importer/`

- `models.py`: Delivery, PhysicalStop, OptimizedRouteStop, Route, ImportResult.
- `xlsx.py`: importação e auditoria das linhas.
- `stops.py`: agrupamento inicial por coordenada.
- `routing.py`: TravelMetric, RoutingProvider, OSRMRoutingProvider e matriz OSRM.
- `types.py`: tipos compartilhados como OptimizationObjective e RouteEndpoint.
- `optimizer.py` / `optimization.py`: otimização determinística; rotas maiores usam greedy + 2-opt.
- `metrics.py`: métricas das pernas e totais usando a mesma matriz da otimização.
- `service.py`: pipeline de aplicação completo.

### Backend

FastAPI em `backend/src/otimizer_api/main.py`.

- POST `/optimize` recebe XLSX e parâmetros.
- CORS configurável por ambiente.
- Limite de upload configurável.
- Erros HTTP tratados para arquivo grande, entrada inválida e falha de roteamento.
- Contrato retorna resumo, pendências, paradas, entregas e pernas.

### Frontend

`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`.

- Mobile-first.
- Upload XLSX.
- Objetivo tempo/distância.
- Origem/destino opcionais.
- Retorno ao início.
- Mapa Leaflet.
- Lista de paradas.
- Detalhes de todas as entregas da parada.
- Navegação por coordenada via Google Maps.
- Botão `SEGUIR PARA A PRÓXIMA`.
- Tratamento de loading, 413, 422, 502 e falha de conexão sem destruir a rota anterior.

## CI confirmado

O GitHub Actions confirmou sucesso nos workflows de Backend e Frontend no commit `f9bb44e8b23b10970be36478666163e847b70700`. O importer também possui execução verde confirmada em histórico anterior.

Não afirmar CI verde para commits posteriores sem consultar novamente as execuções.

## Commits recentes importantes

- `a650b4d9be7bf49e6e3f811ae98ad3e2c5d883c7` — 2-opt para rotas maiores.
- `0c2c6a7fd46c4dbe05abe439657bd6d4ad952ed0` — testes alinhados à abstração canônica de routing provider.
- `d9119902a616772d77985d40b884bf2abbc18e21` — rejeição de workbook sem deliveries válidas.
- `15b04685117ff3c812fc3567037222b1ebf9aea5` — erros claros de API para rotas inválidas.
- `9b259a1ad1e8e811c9bb41f54d54466c5c3d0caf` — testes de edge cases da API/routing.
- `b3e7cd8d5cf3d37e0e6745f9fe23b99e06384e4f` — hardening de estado do frontend.
- `f9bb44e8b23b10970be36478666163e847b70700` — estados visuais do frontend; CI verde confirmado.
- `2672073648c27738c32322ddd2912c74a6b4fc90` — registro da validação dos XLSX reais.

## Ponto de atenção conhecido

Existe ainda `importer/src/otimizer_importer/provider.py`, uma abstração legada paralela. Testes já foram alinhados ao `routing.py` canônico, mas não declarar que o arquivo legado foi removido. Se for consolidar isso, primeiro inspecionar dependências e depois remover/substituir com segurança.

## Próxima sequência recomendada

1. Criar/fortalecer uma regressão automatizada que represente os três casos reais usando apenas dados anonimizados/agregados.
2. Testar o contrato HTTP completo com provider fake nos tamanhos 37, 125 e 131, garantindo preservação de todas as deliveries e PhysicalStops.
3. Medir performance de matriz + otimização para 35/61/90 stops.
4. Executar OSRM real quando houver ambiente de rede disponível e registrar somente métricas, nunca dados pessoais.
5. Evoluir agrupamento de PhysicalStop para tolerância a GPS jitter/endereço, sem mesclar propriedades indevidamente.
6. Evoluir constraints operacionais e solver somente depois de estabilizar o pipeline base.

## Instruções para o próximo chat

Não recomeçar o projeto. Primeiro ler este arquivo, `08_CURRENT_STATE.md`, `09_DECISIONS.md`, `10_TESTS.md` e a implementação atual. Depois consultar os últimos commits/workflows no GitHub. Ao receber `Prossiga`, escolher a próxima etapa acima e implementar de fato, fazendo commit real no GitHub quando possível.

Nunca inventar execução, resultado, commit ou CI. Nunca expor dados reais das planilhas em documentação/testes. 
