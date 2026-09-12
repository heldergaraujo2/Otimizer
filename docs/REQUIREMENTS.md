# Requisitos do Otimizer

## Regras funcionais

- Importar arquivos XLSX de entregas.
- Considerar elegível toda linha que possua latitude e longitude válidas.
- Nunca excluir uma entrega apenas porque `Sequence` ou `Stop` está vazio ou contém `-`.
- Tratar `Sequence` e `Stop` da origem como referência, não como autoridade sobre a rota.
- Reconstruir paradas físicas a partir da localização real, preservando todas as entregas vinculadas.
- Não agrupar locais fisicamente distintos apenas porque compartilham o mesmo `Stop` de origem.
- Calcular custos de deslocamento usando rede viária real e direção das vias.
- Gerar uma numeração própria para cada parada física na rota otimizada.
- Exibir marcadores numerados no mapa.
- Exibir detalhes da parada e todas as entregas/pacotes associados.
- Permitir avançar para a próxima parada.
- Exibir contagens de entregas importadas, paradas físicas, paradas roteadas e pendências.
- Permitir origem/depósito configurável e destino opcional.

## Invariantes

### Cobertura de entregas

Toda linha com latitude e longitude válidas deve aparecer em alguma parada física da rota final.

### Integridade de agrupamento

Uma parada física pode conter várias entregas, mas nenhuma entrega pode desaparecer ou ser duplicada durante importação, agrupamento ou otimização.

### Numeração

A numeração exibida ao motorista é gerada pelo Otimizer e não depende da `Sequence` ou `Stop` originais.

## Qualidade

O desenvolvimento deve usar os arquivos XLSX reais fornecidos pelo projeto como casos de regressão locais, sem publicar dados pessoais ou de entrega em repositório público sem autorização explícita.
