# Arquitetura inicial

## Princípio

A arquitetura separa a entrega individual da parada física e da posição da parada na rota.

```text
Delivery (linha XLSX)
      ↓
PhysicalStop (local físico)
      ↓
OptimizedRouteStop (ordem Otimizer)
```

## Pipeline

```text
XLSX
  → Importação
  → Validação
  → Normalização
  → Registro de deliveries
  → Reconstrução de paradas físicas
  → Matriz de custos de rede viária
  → Otimização
  → Numeração da rota
  → Mapa operacional
  → Navegação para próxima parada
```

## Responsabilidades

### Importer
Lê XLSX, identifica colunas, normaliza tipos e preserva os valores originais necessários para auditoria.

### Domain
Mantém `Delivery`, `PhysicalStop`, `Route` e seus vínculos. Uma entrega não pode ser perdida durante agrupamento.

### Stop reconstruction
Determina quando várias entregas representam o mesmo local físico. `Sequence` e `Stop` da origem não comandam essa decisão.

### Routing
Obtém tempos/distâncias de deslocamento pela rede viária real, incluindo restrições de direção e vias de mão única.

### Optimization
Resolve a ordem das paradas com base nos custos de condução. A origem/depósito e o destino opcional são parâmetros da rota.

### Presentation
Mostra mapa, marcadores numerados, lista de paradas, detalhes e ação para seguir para a próxima parada.

## Mobile-ready

A primeira implementação será web-first e responsiva, mas contratos de domínio e API não devem depender da interface desktop. Isso permite evoluir para PWA/Android sem reescrever o núcleo de importação, agrupamento e otimização.

## Privacidade

Dados de endereço, CEP e códigos de rastreio devem ser tratados como dados operacionais sensíveis. Fixtures públicos devem ser anonimizados.
