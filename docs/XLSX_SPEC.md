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

Alguns futuros exports podem também fornecer:

- `Quadra`
- `Lote`

`Quadra` e `Lote` são campos opcionais de localização. Quando presentes, devem ser preservados e cruzados com endereço, CEP e coordenadas para melhorar a identificação do imóvel e do ponto de parada.

## Regra de elegibilidade

Uma linha é elegível para roteamento quando `Latitude` e `Longitude` podem ser interpretadas como coordenadas geográficas válidas.

`Sequence` e `Stop` não são campos obrigatórios para elegibilidade.

A ausência de `Quadra` ou `Lote` também não invalida uma linha.

## Semântica dos campos de origem

- `Sequence`: referência da ordem original.
- `Stop`: referência do agrupamento original.
- `SPX TN`: identificador de rastreio/pacote.
- endereço, bairro, cidade e CEP: informações da localização e apresentação.
- `Quadra` e `Lote`: evidências cadastrais do imóvel, quando disponíveis.
- latitude/longitude: coordenadas geográficas recebidas e base espacial inicial.

## Reconciliação da localização

O Otimizer não deve assumir que latitude/longitude isoladas representam o ponto exato onde o motorista deve parar.

A localização da entrega deve poder ser refinada pelo cruzamento de:

```text
endereço + bairro + cidade + CEP
+ quadra + lote (quando disponíveis)
+ latitude + longitude
```

Essas informações são evidências complementares. Coordenadas continuam sendo a referência espacial, enquanto endereço/quadra/lote ajudam a identificar o imóvel correto e a evitar agrupamentos incorretos quando pontos GPS forem imprecisos ou conflitantes.

A evolução futura da camada de geolocalização poderá ainda transformar o ponto do imóvel em um ponto de acesso/parada na via, evitando navegar o motorista para dentro de um lote ou terreno quando o acesso correto estiver na rua.

## Regras de preservação

Cada linha elegível deve gerar exatamente uma `Delivery` no domínio, com vínculo rastreável à parada física correspondente.

Uma parada física pode conter uma ou várias deliveries.

O processamento deve preservar os campos originais necessários para auditoria e exibição ao motorista, incluindo `Quadra` e `Lote` quando existirem no arquivo.

## Linhas com `-`

Valores `-` em `Sequence` ou `Stop` são tratados como ausência de informação de origem. Eles não invalidam uma linha que tenha latitude e longitude válidas.

## Auditoria

O resultado da importação deve permitir comparar:

```text
linhas XLSX
→ deliveries elegíveis
→ deliveries inválidas/pendentes
→ evidências de localização
→ paradas físicas
→ paradas roteadas
```

O objetivo é tornar impossível uma perda silenciosa de entregas e permitir que a precisão da localização seja aprimorada sem sacrificar a rastreabilidade da linha original.
