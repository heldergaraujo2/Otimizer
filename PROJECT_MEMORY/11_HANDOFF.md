# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Objetivo

Transformar XLSX reais de entregas em rotas confiáveis pela rede viária real, preservando todas as entregas válidas e buscando a localização física mais precisa possível.

Fluxo principal:

`XLSX → Delivery → evidências → localização → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Regras de negócio obrigatórias

- Nenhuma entrega válida pode ser descartada por ausência de GPS.
- `0,0` e coordenadas inválidas devem ser tratadas como GPS ausente.
- Usar todas as evidências disponíveis: latitude, longitude, endereço, número, quadra, lote, bairro, cidade, CEP e complemento.
- A identidade de `PhysicalStop` não depende somente de latitude/longitude.
- `Sequence` e `Stop` da planilha não determinam a ordem final.
- Conflitos explícitos de endereço/número/quadra/lote devem impedir fusões inseguras.
- Propriedade, acesso viário e ponto aproximado de rua são conceitos diferentes.
- Custos de rota devem vir da malha viária, não de distância em linha reta.
- Todas as paradas válidas devem permanecer representadas no resultado; problemas de localização/roteamento devem ser tratados individualmente.
- Uma parada problemática nunca deve derrubar a otimização das demais.
- Quando a rua correta puder ser determinada com confiança suficiente, um ponto aproximado na rua é preferível a excluir a entrega.

## Estado atual — validado no PC

### Importação e otimização XLSX

O usuário realizou teste real com **mais de 30 arquivos XLSX reais**.

Resultado informado pelo usuário:

- todos os arquivos foram importados/otimizados corretamente;
- paradas não encontradas não derrubaram as demais paradas;
- as paradas que ficaram pendentes puderam ser adicionadas manualmente;
- após a inclusão manual, a rota foi recalculada/reotimizada sem problemas;
- o fluxo foi considerado **100% funcional conforme esperado**.

Esse resultado deve ser tratado como validação funcional real já concluída, e não como hipótese.

### Localização cadastral / fallback

Goiânia utiliza fontes municipais oficiais para dados cadastrais e logradouros. O fluxo contém resolução cadastral e fallback de logradouro municipal.

Quando o ponto exato do imóvel não puder ser determinado, a regra é preservar a entrega e usar a melhor evidência disponível, inclusive ponto aproximado na rua correta quando aplicável.

### Rota manual

O autocomplete de rua consulta em tempo real a base municipal de Goiânia, especialmente o layer `10 — Logradouro por Bairro`.

Fluxo validado no PC:

`digitar rua → sugestões reais municipais → selecionar rua → adicionar parada → alfinete automático sobre a rua → ajuste manual opcional → otimização`

O usuário confirmou que:

- ruas reais foram encontradas;
- paradas foram adicionadas;
- o alfinete automático apareceu corretamente;
- o comportamento funcionou perfeitamente.

A posição automática é um ponto da geometria da rua, não uma alegação de que o ponto seja a porta do imóvel. O clique manual continua disponível para ajuste fino.

## Implementação relevante recente

O estado atual da branch `main` inclui, além da implementação municipal e de recuperação de pendências, os seguintes ajustes de auditoria:

- `94a6ae200cf7452171c1460f0ee77ac2ffb7492a` — alinhamento do teste frontend com o contrato atual de coordenadas opcionais;
- `a5bc93e78a26d72605acef3f3996a13c72123971` — alinhamento do fixture de evidência municipal com o modelo atual;
- `78edea8704ecfd7d96a094cfcb985c8babd09dff` — teste do fallback municipal validando que o ponto pertence à geometria da rua, sem exigir um vértice/midpoint específico.

Esses ajustes são de teste/contrato e não removem nem alteram as funcionalidades já validadas no PC.

## Auditoria automatizada atual

No commit `78edea8704ecfd7d96a094cfcb985c8babd09dff`, os workflows do GitHub Actions confirmaram:

- Importer: **128 passed**;
- Backend: **71 passed, 2 warnings**;
- Frontend: **sucesso**, incluindo validação de sintaxe e execução de todos os testes frontend.

Uma falha anterior do Importer foi reproduzida no CI e investigada antes da correção: os testes do fallback municipal estavam desatualizados em relação ao construtor atual de `LocationEvidence` e depois em relação ao contrato real de ponto sobre a geometria da rua. Não houve evidência de falha do fluxo de produção; os testes foram corrigidos para representar o contrato efetivo.

Warnings atuais conhecidos do backend vêm da compatibilidade `starlette.testclient`/`httpx` e do alias `anyio` usado pela dependência. Não foram alterados sem necessidade de correção estrutural comprovada.

## Testes automatizados conhecidos

Os números históricos `123 passed` / `63 passed` não devem mais ser usados como estado atual. O último CI validado é o descrito acima.

Os testes devem continuar sendo executados novamente após qualquer alteração estrutural.

## Ambiente local conhecido

Windows:

`D:\Otimizer\Otimizer-main`

Python:

`3.14.7`

Backend:

```powershell
cd D:\Otimizer\Otimizer-main
.\.venv\Scripts\Activate.ps1
python -m uvicorn otimizer_api.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd D:\Otimizer\Otimizer-main
python -m http.server 8080 --directory frontend
```

URL:

`http://localhost:8080`

## Próxima fase

A validação funcional básica e o teste real de mais de 30 XLSX já foram concluídos com sucesso. A próxima etapa é **auditoria de robustez e preparação do produto**, sem recomeçar o projeto.

Prioridades:

1. verificar o estado atual completo do Git e consistência entre código/documentação;
2. manter todas as suítes automatizadas verdes;
3. auditar regressões em importer, backend, routing, optimization e frontend;
4. auditar tratamento de dados incompletos/conflitantes;
5. auditar pernas não roteáveis sem permitir falha da rota inteira;
6. auditar repetibilidade/determinismo da otimização;
7. auditar performance com arquivos maiores;
8. revisar falhas de serviços externos e timeouts;
9. revisar segurança/autenticação/licenciamento;
10. manter README, documentação e `PROJECT_MEMORY` coerentes;
11. somente depois avançar para novas capacidades de produto.

## Regra de continuidade

Não recomeçar o projeto.

Para cada alteração significativa:

`verificar estado → uma alteração → testes → análise → diff → commit → push → confirmação no GitHub → próxima etapa`

Nunca inventar execução, resultado, commit ou CI.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.

O objetivo agora é transformar a validação funcional já comprovada em uma base robusta e auditada para evolução do produto.
