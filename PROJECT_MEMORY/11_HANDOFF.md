# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch principal `main`.

## Objetivo do produto

Transformar planilhas XLSX de entregas em uma rota real otimizada por rede viária, preservando 100% das entregas válidas e buscando a localização física mais precisa possível:

XLSX -> importação -> validação -> Delivery -> evidências de endereço -> resolução cadastral/geográfica -> PhysicalStop -> matriz rodoviária -> otimização -> sequência -> mapa -> detalhes -> navegação.

## Estratégia geográfica

O desenvolvimento inicial será concentrado em Goiânia para permitir validação com dados cadastrais/geográficos reais, mas o núcleo não pode depender de Goiânia. A arquitetura deve permitir providers específicos por cidade/estado posteriormente.

Foram identificadas fontes oficiais da Prefeitura de Goiânia com dados de lotes, quadras e camadas de Número Predial Oficial, Segmento de Logradouro e Logradouro. Essas fontes serão usadas como base para o futuro `GoianiaLocationProvider`, sem colocar dados cadastrais reais de clientes no repositório.

## Regras de domínio que NÃO podem ser quebradas

- Toda linha com latitude e longitude válidas é uma Delivery e deve ser preservada exatamente uma vez.
- `Sequence` e `Stop` da planilha são informativos; nunca usar esses campos para decidir inclusão ou ordem final.
- Delivery nunca é mesclada nessa camada.
- PhysicalStop representa uma localização física e pode conter várias Deliveries.
- Coordenadas iguais podem ser agrupadas em um PhysicalStop; coordenadas diferentes permanecem separadas, salvo reconciliação segura por evidências de localização.
- Quadra/Lote são opcionais. Número residencial também é opcional.
- O endereço original nunca deve ser destruído ou substituído pelo valor parseado.
- Toda evidência disponível deve poder participar da resolução: GPS, endereço, número, quadra, lote, CEP, bairro, cidade e complemento.
- Localização da propriedade e ponto de acesso viário são conceitos distintos; o sistema não deve fingir que o GPS da planilha já é o ponto ideal de parada do veículo.
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
- Os arquivos reais não possuem colunas separadas obrigatórias de Quadra/Lote; essas informações aparecem embutidas em `Destination Address` em vários formatos.

Detalhes agregados e seguros estão em `PROJECT_MEMORY/12_REAL_XLSX_VALIDATION.md`.

## Arquitetura atual

### Importer

`importer/src/otimizer_importer/`

- `models.py`: Delivery, PhysicalStop, OptimizedRouteStop, Route, ImportResult.
- `address_parser.py`: parser brasileiro conservador para número, Quadra e Lote e normalização de endereço.
- `xlsx.py`: importação e auditoria das linhas; agora enriquece Delivery com evidências extraídas do endereço.
- `location.py`: abstração `LocationDataProvider`, `LocationEvidence`, `ResolvedLocation` e fallback seguro para GPS original.
- `stops.py`: agrupamento por coordenada com reconciliação conservadora por endereço/Quadra/Lote.
- `routing.py`: TravelMetric, RoutingProvider, OSRMRoutingProvider e matriz OSRM com batching.
- `types.py`: tipos compartilhados como OptimizationObjective e RouteEndpoint.
- `optimizer.py` / `optimization.py`: otimização determinística; rotas maiores usam greedy + 2-opt.
- `metrics.py`: métricas das pernas e totais usando a mesma matriz da otimização.
- `service.py`: pipeline de aplicação completo e invariantes de cobertura.

### Backend

FastAPI em `backend/src/otimizer_api/main.py`.

- POST `/optimize` recebe XLSX e parâmetros.
- CORS configurável por ambiente.
- Limite de upload configurável.
- Erros HTTP tratados para arquivo grande, entrada inválida e falha de roteamento.
- Contrato retorna resumo, pendências, paradas, entregas e pernas.
- Quadra/Lote já podem ser expostos na entrega; a próxima evolução é expor também evidências de localização/resolução.

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

## CI

No momento do fechamento desta fase, os workflows `Importer tests` e `Frontend tests` para o commit `fbae392503099a0f1b14c7918777f090e3a1c6a0` foram disparados por push e estavam em estado `queued`. Não declarar sucesso antes de consultar novamente.

## Commits recentes importantes desta fase

- `7410249f8059d60d22b6fd2a0fc931d46934e906` — parser brasileiro de evidências de endereço.
- `e04ff96f49bdace7216b227d509aa585e776b752` — campos enriquecidos de endereço em Delivery.
- `f24866113fd0ed2ecae96dd12991165c96364297` — parser integrado à importação XLSX.
- `056cecb23ecfe53507c6f0c18daf7f8931cd8141` — testes sintéticos do parser.
- `2a215485124b138c82f0b574d865db67ee388088` — abstração de resolução de localização.
- `fbae392503099a0f1b14c7918777f090e3a1c6a0` — exports públicos das abstrações de localização.

## Próxima sequência recomendada

1. Confirmar CI do commit `fbae392...` e corrigir regressões, se houver.
2. Criar `GoianiaLocationProvider` real, começando pela camada oficial de Número Predial/Lotes/Quadras/Logradouros.
3. Criar cache/index local das geometrias para evitar depender de chamadas remotas a cada entrega.
4. Implementar resolução por evidências com score de confiança e manter GPS original, ponto da propriedade e ponto de acesso separados.
5. Criar testes sintéticos de resolução para: somente número; quadra+lote; quadra+lote+número; endereço+GPS; GPS com pequena divergência; endereço incompleto.
6. Integrar localização resolvida ao PhysicalStop e depois ao routing, sem perder a coordenada original.
7. Medir precisão e performance em Goiânia antes de criar providers para outras cidades/estados.
8. Depois estabilizar constraints operacionais, solver e demais funcionalidades avançadas.

## Ponto de atenção conhecido

Existe ainda `importer/src/otimizer_importer/provider.py`, uma abstração legada paralela. Testes já foram alinhados ao `routing.py` canônico, mas não declarar que o arquivo legado foi removido.

## Instruções para o próximo chat

Não recomeçar o projeto. Primeiro ler este arquivo, `08_CURRENT_STATE.md`, `09_DECISIONS.md`, `10_TESTS.md` e a implementação atual. Depois consultar os últimos commits/workflows no GitHub. Ao receber `Prossiga`, escolher a próxima etapa acima e implementar de fato, fazendo commit real no GitHub quando possível.

Nunca inventar execução, resultado, commit ou CI. Nunca expor dados reais das planilhas em documentação/testes.
