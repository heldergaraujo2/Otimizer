# Validação dos XLSX reais

Data: 12/09/2026

Os três arquivos XLSX de referência foram lidos diretamente no ambiente de execução. O conteúdo de endereços e rastreios não é reproduzido neste documento.

## Resultado

| Caso | Entregas | Paradas por coordenada (6 casas) | Grupos duplicados | Máximo no mesmo ponto | Sequence ausente/`-` | Stop ausente/`-` |
|---|---:|---:|---:|---:|---:|---:|
| 12-09-2026 — 125 entregas | 125 | 61 | 16 | 37 | 2 | 2 |
| (1)12-09-2026 — 37 entregas | 37 | 35 | 2 | 2 | 14 | 14 |
| 11-09-2026 — 131 entregas | 131 | 90 | 24 | 8 | 3 | 3 |

## Invariantes observadas

- 293/293 linhas de dados possuem latitude e longitude numéricas válidas.
- `Sequence` e `Stop` podem estar ausentes ou conter `-`; portanto não devem controlar inclusão nem ordenação final.
- Existem múltiplas entregas no mesmo ponto físico; Delivery não deve ser fundida em uma única entidade.
- O caso de 125 entregas possui um agrupamento de 37 entregas no mesmo ponto, importante para testes de escala e interface.
- O agrupamento por coordenada produz 61, 35 e 90 PhysicalStops respectivamente.

## Limitação

Esta validação comprova leitura, estrutura, coordenadas e comportamento esperado do agrupamento nos arquivos reais. Ela não comprova uma execução contra OSRM externo; essa etapa requer acesso de rede ao serviço de roteamento.

## Regra para continuidade

Nunca adicionar endereços, CEPs ou números de rastreio reais a fixtures, documentação ou testes. Usar apenas os agregados acima para regressão, mantendo os arquivos reais como dados de referência fora da suíte automatizada.
