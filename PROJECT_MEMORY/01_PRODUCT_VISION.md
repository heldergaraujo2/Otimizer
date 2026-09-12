# Visão do Produto

O Otimizer deve transformar dados de entregas em uma rota de condução prática para o motorista.

## Experiência principal

1. Motorista importa um XLSX.
2. Sistema informa quantas entregas foram encontradas e quantas possuem coordenadas válidas.
3. Sistema reconstrói as paradas físicas sem confiar cegamente no agrupamento da origem.
4. Sistema calcula custos de deslocamento pela malha viária.
5. Sistema otimiza a ordem.
6. Motorista visualiza uma rota numerada no mapa.
7. Ao abrir uma parada, vê o local e todas as entregas associadas.
8. Pode avançar diretamente para a próxima parada.

## O que significa sucesso

O motorista deve conseguir olhar para a rota e confiar que:

- nenhuma entrega elegível foi esquecida;
- entregas no mesmo local não foram artificialmente espalhadas;
- locais diferentes não foram indevidamente fundidos;
- a ordem considera a condução real;
- a numeração é clara e operacional.

## Evolução planejada

A primeira versão prioriza importação, reconstrução de paradas, roteamento, otimização e mapa. GPS contínuo, navegação turn-by-turn, offline e recursos avançados entram depois sem quebrar o núcleo.
