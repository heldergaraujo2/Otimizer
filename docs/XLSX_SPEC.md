# Especificação XLSX

## Colunas observadas

Os arquivos de entrega utilizados no projeto apresentam:

- `AT ID`
- `Sequence`
- `Stop`
- `SPX TN`
- `Destination Address`
- `Bairro`
- `City`
- `Zipcode/Postal code`
- `Latitude`
- `Longitude`

## Regra de elegibilidade

Uma linha é elegível para roteamento quando `Latitude` e `Longitude` podem ser interpretadas como coordenadas geográficas válidas.

`Sequence` e `Stop` não são campos obrigatórios para elegibilidade.

## Semântica dos campos de origem

- `Sequence`: referência da ordem original.
- `Stop`: referência do agrupamento original.
- `SPX TN`: identificador de rastreio/pacote.
- endereço, bairro, cidade e CEP: informações da localização e apresentação.
- latitude/longitude: base inicial para identificação do local físico e roteamento.

## Regras de preservação

Cada linha elegível deve gerar exatamente uma `Delivery` no domínio, com vínculo rastreável à parada física correspondente.

Uma parada física pode conter uma ou várias deliveries.

O processamento deve preservar os campos originais necessários para auditoria e exibição ao motorista.

## Linhas com `-`

Valores `-` em `Sequence` ou `Stop` são tratados como ausência de informação de origem. Eles não invalidam uma linha que tenha latitude e longitude válidas.

## Auditoria

O resultado da importação deve permitir comparar:

```text
linhas XLSX
→ deliveries elegíveis
→ deliveries inválidas/pendentes
→ paradas físicas
→ paradas roteadas
```

O objetivo é tornar impossível uma perda silenciosa de entregas.
