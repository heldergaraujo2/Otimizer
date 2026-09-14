# Primeiro teste real no PC

Objetivo: validar o fluxo real **XLSX → API → rota → mapa** usando um arquivo exportado real, sem substituir os testes automatizados.

## 1. Pré-requisitos

- Python 3.11 ou superior
- Git
- navegador moderno
- conexão com a internet para o roteamento OSRM

## 2. Atualizar o projeto

```bash
git pull origin main
```

## 3. Criar ambientes virtuais

No diretório do projeto:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```bat
.venv\Scripts\activate.bat
```

## 4. Instalar backend e importer

```bash
python -m pip install -e "./importer[test]"
python -m pip install -e "./backend[test]"
```

## 5. Rodar a API

Em um terminal:

```bash
python -m uvicorn otimizer_api.main:app --app-dir backend/src --reload
```

A API deve ficar em `http://localhost:8000`.

## 6. Abrir a interface

Abra `frontend/index.html` no navegador.

Se o navegador bloquear requisições `file://` por política local, sirva a pasta frontend com um servidor HTTP simples:

```bash
python -m http.server 8080 --directory frontend
```

Depois abra `http://localhost:8080`.

## 7. Executar o teste real

1. Selecione um dos XLSX exportados reais na raiz do projeto.
2. Escolha o objetivo da rota.
3. Opcionalmente informe origem e/ou destino.
4. Clique em **Otimizar rota**.
5. Confirme no resultado:
   - quantidade de entregas roteadas;
   - quantidade de paradas físicas;
   - distância e duração;
   - `0` pendências para um arquivo com coordenadas válidas;
   - cobertura completa;
   - marcadores numerados no mapa;
   - detalhes da parada;
   - navegação para a parada.

## 8. Critério de aprovação da primeira fase

O teste é considerado aprovado quando o mesmo arquivo usado como entrada mantém todas as entregas válidas, nenhuma entrega desaparece durante o agrupamento, todas as paradas físicas são roteadas e a interface apresenta a sequência final sem erro.

Falha de OSRM, indisponibilidade de internet ou erro de navegador deve ser registrada separadamente de uma falha de importação/agrupamento/otimização.

## 9. Testes automatizados antes do teste manual

No diretório `importer`:

```bash
python -m pytest -q
```

No diretório `backend`:

```bash
python -m pytest -q
```

Os três XLSX reais também possuem uma regressão automatizada de contabilização de entregas e PhysicalStops em `tests/test_real_exports.py`.
