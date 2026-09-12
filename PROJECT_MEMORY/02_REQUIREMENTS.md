# Requisitos consolidados

## Dados

- Entrada: XLSX de entregas.
- Cada linha elegível representa uma `Delivery`.
- Coordenadas válidas são o critério de inclusão para roteamento.
- `Sequence` e `Stop` da origem são metadados de referência.

## Parada física

- Uma `PhysicalStop` representa um local real.
- Várias deliveries no mesmo local podem compartilhar a parada.
- Todas as deliveries continuam preservadas individualmente.
- Mesmo `Stop` de origem não significa necessariamente mesmo local físico.

## Rota

- O Otimizer gera sua própria sequência.
- Cada parada física roteada recebe um número único.
- O custo deve vir de roteamento viário real.
- Origem/depot é configurável.
- Destino é opcional para permitir rotas abertas ou fechadas.

## Interface

- Mapa com marcadores 1..N.
- Lista de paradas.
- Detalhes da parada.
- Contagem de deliveries associadas.
- Identificadores de rastreio associados.
- Ação para seguir para a próxima parada.
- Totais de importação, paradas físicas, roteadas e pendências.

## Qualidade

A cobertura é mais importante que uma otimização agressiva: uma rota ligeiramente menos eficiente, mas completa e auditável, é preferível a uma rota que silenciosamente deixe uma entrega para trás.
