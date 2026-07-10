# Checklist De Release

Este checklist documenta o caminho local para validar e gerar uma build do PhotoVault. Ele assume Windows, `.venv` no root do projeto e dependencias ja instaladas.

## 1. Pre-Flight

Confirme que o repositorio esta limpo ou que as alteracoes atuais sao intencionais:

```powershell
git status --short --branch
```

Confirme ferramentas basicas:

```powershell
.\.venv\Scripts\python.exe --version
node --version
npm.cmd --version
cargo --version
```

ExifTool e opcional. Quando instalado no PATH, o app habilita enriquecimento rico:

```powershell
exiftool -ver
```

## 2. Testes

Python:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp
```

Filtros TypeScript:

```powershell
cd frontend
npm.cmd run test:filters
```

## 3. Build Frontend

```powershell
cd frontend
npm.cmd run build
```

Saida esperada:

```text
frontend\dist\
```

## 4. Checagem Tauri/Rust

```powershell
cd frontend\src-tauri
cargo check
```

## 5. Preparar Sidecars De Release

O release atual usa um executavel auxiliar gerado por PyInstaller para que o app nao dependa da `.venv` do repositorio em outra maquina. Os binarios gerados ficam em `frontend\src-tauri\resources\` e nao sao versionados.

```powershell
cd <repo>
New-Item -ItemType Directory -Force frontend\src-tauri\resources
Copy-Item frontend\node_modules\ffmpeg-ffprobe-static\ffmpeg.exe frontend\src-tauri\resources\ffmpeg.exe -Force
Copy-Item frontend\node_modules\ffmpeg-ffprobe-static\ffprobe.exe frontend\src-tauri\resources\ffprobe.exe -Force
New-Item -ItemType Directory -Force frontend\src-tauri\resources\exiftool
Copy-Item $env:USERPROFILE\.photovault\tools\exiftool.exe frontend\src-tauri\resources\exiftool\exiftool.exe -Force
Copy-Item $env:USERPROFILE\.photovault\tools\exiftool_files frontend\src-tauri\resources\exiftool\exiftool_files -Recurse -Force
.\.venv\Scripts\pyinstaller.exe --clean --onefile --name photovault-bridge --distpath frontend\src-tauri\resources --workpath build\pyinstaller --specpath build\pyinstaller bridge.py
```

Smoke test da bridge empacotada:

```powershell
'{}' | frontend\src-tauri\resources\photovault-bridge.exe diagnostics
```

Observacao: o instalador de teste inclui Python/bridge, ffmpeg, ffprobe e ExifTool para permitir validacao em uma maquina Windows sem ambiente de desenvolvimento.

## 6. Build Desktop Debug

```powershell
cd frontend
npx.cmd tauri build --debug --no-bundle
```

Binario debug esperado:

```text
frontend\src-tauri\target\debug\app.exe
```

## 7. Build Desktop Release

Quando o fluxo debug estiver validado:

```powershell
cd frontend
npx.cmd tauri build
```

Artefatos esperados ficam em:

```text
frontend\src-tauri\target\release\
frontend\src-tauri\target\release\bundle\
```

## 8. Smoke Test Manual

Antes de publicar uma release:

1. Abrir o app.
2. Confirmar que o estado carrega sem erro.
3. Configurar ou abrir um vault existente.
4. Analisar uma pasta pequena de teste.
5. Revisar decisoes.
6. Executar importacao.
7. Abrir Galeria.
8. Gerar previews.
9. Abrir/localizar um arquivo no Explorer.
10. Conferir Logs.
11. Rodar enriquecimento se ExifTool estiver disponivel.

## 9. Publicacao No GitHub

Depois da validacao:

```powershell
git status --short --branch
git log --oneline --decorate -5
git push origin main
```

Para releases versionadas, criar tag depois de decidir o numero da versao:

```powershell
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Pontos Ainda A Resolver

- Validar o sidecar PyInstaller em maquina Windows limpa.
- Automatizar parte do checklist em script ou CI.
- Decidir formato de release: instalador, zip portavel ou ambos.
- Definir estrategia final de licenca/distribuicao para ffmpeg/ffprobe antes de release publica.
