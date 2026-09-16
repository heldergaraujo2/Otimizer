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

Além da implementação municipal, recuperação de pendências e proteção de seleção municipal obsoleta, a auditoria atual adicionou uma proteção específica na seleção cadastral:

- candidatos do Cadastro Imobiliário que contradizem evidência explícita de quadra, lote, número, bairro ou rua não são aceitos;
- quando, para uma entrega sem GPS, existem registros cadastrais para a quadra+lote informados, mas todos contradizem a evidência explícita, a entrega é colocada em quarentena como não resolvida em vez de cair para uma associação cadastral de lote mais fraca;
- a entrega não é removida: permanece disponível para resolução posterior/manual;
- candidatos compatíveis continuam seguindo a hierarquia cadastral existente, incluindo ponto do imóvel e acesso viário.

Commits desta alteração:

- `975e35f460d005af7bf94b350eb1b088c56b56a8` — proteção de conflito cadastral no runtime;
- `d89648771ff00c4c2309d8fd80c2521b89edb8a6` — testes de conflito explícito de número/rua e preservação da resolução compatível.

## Auditoria automatizada atual

No commit `d89648771ff00c4c2309d8fd80c2521b89edb8a6`, os três workflows do GitHub Actions executaram com sucesso:

- Importer: **132 passed em 3.82s**;
- Backend: **71 passed, 2 warnings em 3.43s**;
- Frontend: **success**, incluindo validação de sintaxe e todos os testes frontend.

O Importer aumentou de 128 para 132 testes com a nova cobertura de conflito cadastral.

Os warnings atuais conhecidos do Backend são de compatibilidade/depreciação em `starlette.testclient`/`httpx` e alias do `anyio`; não foram alterados nesta etapa porque não há evidência de falha funcional decorrente deles.

Os workflows foram verificados diretamente no GitHub para o SHA `d89648771ff00c4c2309d8fd80c2521b89edb8a6`; não houve apenas inferência pelo estado do commit.

## Cobertura automatizada relevante

### XLSX e preservação

- linhas vazias;
- preservação das entregas;
- importação real já validada com mais de 30 arquivos;
- cenários de localização incompleta.

### Localização

- GPS;
- ausência de GPS;
- cadastro;
- quadra/lote;
- ponto cadastral;
- acesso viário;
- fallback de rua;
- proveniência/confiança;
- ponto municipal aproximado;
- conflito explícito de número/rua sem associação insegura.

### Stops

- diferenciação entre `Delivery` e `PhysicalStop`;
- proteção contra fusões incompatíveis;
- preservação de pendentes;
- entrega problemática permanece representada.

### Routing

- matriz OSRM;
- pares inacessíveis;
- pernas individuais sem rota;
- preservação de todas as paradas.

### Optimization

- origem;
- destino;
- retorno;
- determinismo;
- rotas grandes;
- parada inacessível;
- preservação de 100/100 entregas no cenário isolado;
- reotimização manual.

### Frontend

- autocomplete municipal;
- alfinete municipal;
- invalidação de seleção municipal obsoleta;
- ajuste manual;
- navegação;
- pendências.

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

A validação funcional básica, o teste real de mais de 30 XLSX e a primeira proteção concreta de conflito cadastral já foram concluídos com sucesso. A próxima etapa continua sendo **auditoria de robustez e preparação do produto**, sem recomeçar o projeto.

Prioridades restantes:

1. verificar o estado atual completo do Git e consistência entre código/documentação;
2. manter todas as suítes automatizadas verdes;
3. auditar regressões em importer, backend, routing, optimization e frontend;
4. auditar outros conflitos de evidência cadastral e casos de empate;
5. auditar múltiplas pernas não roteáveis sem permitir falha da rota inteira;
6. auditar repetibilidade/determinismo da otimização em cenários adicionais;
7. auditar performance com arquivos maiores;
8. revisar falhas de serviços externos e timeouts;
9. revisar segurança/autenticação/licenciamento;
10. manter README, documentação e `PROJECT_MEMORY` coerentes;
11. somente depois avançar para novas capacidades de produto.

## Próximo ajuste técnico

O conflito explícito de número/rua que motivou a etapa atual está protegido e coberto por testes.

Não considerar a auditoria inteira concluída ainda. Continuar examinando a hierarquia de localização sem reduzir precisão nem criar associações inseguras.

Depois de cada alteração significativa:

`verificar estado → uma alteração → testes → análise → diff → commit → push → confirmação no GitHub → próxima etapa`

## Regra de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.

O objetivo agora é transformar a validação funcional já comprovada em uma base robusta e auditada para evolução do produto.
