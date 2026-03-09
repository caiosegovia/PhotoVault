# PhotoVault

**Organizador de fotos e vídeos para Windows** — classifica automaticamente sua biblioteca de mídia por data, detecta duplicatas e mantém um histórico completo de cada sessão.

---

## Funcionalidades

| Recurso | Detalhe |
|---|---|
| **Organização automática** | Copia ou move arquivos para pastas estruturadas por data (`2024/01/foto.jpg`) |
| **Padrões customizáveis** | `{year}/{month:02d}`, `{year}/{month_name}`, `{year}`, por câmera e outros |
| **Preview antes de executar** | Visualize exatamente o que será feito antes de mover qualquer arquivo |
| **Detecção de duplicatas exatas** | SHA-256 em 3 camadas (tamanho → partial hash → full hash) |
| **Detecção de duplicatas visuais** | pHash perceptual com threshold configurável |
| **Índice de destino cacheado** | SQLite guarda hashes do destino; execuções subsequentes são instantâneas |
| **Execução paralela** | 1 / 2 / 4 / 8 workers configuráveis com pause e cancel |
| **Verificação de integridade** | Modo SHA-256 pós-cópia opcional |
| **Relatório exportável** | HTML com estatísticas completas da sessão |
| **Dashboard com histórico** | Gráficos de arquivos por ano, sessões recentes, espaço utilizado |
| **Google Photos** | Download via OAuth2 (opcional) |

---

## Interface

O app segue um fluxo linear de 7 etapas:

```
Dashboard → Fontes → Regras → Preview → Duplicatas → Execução → Relatório
```

Cada etapa pode ser revisitada a qualquer momento pelo menu lateral.

---

## Requisitos

- **Windows 10/11** (64-bit)
- Para executar o `.exe`: nenhum requisito adicional
- Para desenvolvimento: Python 3.12+

---

## Instalação (usuário final)

1. Baixe a última release em **Releases**
2. Extraia `PhotoVault.zip`
3. Execute `PhotoVault.exe`

Nenhuma instalação necessária. Dados salvos em `%USERPROFILE%\.photovault\`.

---

## Desenvolvimento

### 1. Clonar e criar ambiente

```bash
git clone https://github.com/caiosegovia/PhotoVault.git
cd PhotoVault
python -m venv .venv_win
.venv_win\Scripts\activate
pip install -r requirements.txt
```

### 2. Executar (requer display — Windows ou WSLg)

```bash
python main.py
```

### 3. Compilar o executável

```bat
build.bat
```

O executável é gerado em `dist\PhotoVault\PhotoVault.exe`.

---

## Estrutura do projeto

```
PhotoVault/
├── main.py                        # Entrypoint
├── build.bat                      # Build PyInstaller
├── requirements.txt
│
├── core/
│   ├── database.py                # SQLite (WAL mode, tabelas files/sessions/destination_index)
│   ├── scanner.py                 # Varredura de diretórios
│   ├── organizer.py               # Planejamento e execução de operações
│   ├── deduplicator.py            # Detecção de duplicatas (SHA-256 + pHash)
│   ├── metadata.py                # Extração de data EXIF / hachoir / ffprobe
│   └── patterns.py                # Padrões de organização
│
├── gui/
│   ├── app.py                     # CTk app, constantes de cor/fonte, app_state
│   ├── main_window.py             # Janela principal, sidebar, navegação
│   └── views/
│       ├── dashboard.py           # Cards de estatísticas, gráficos, sessões
│       ├── sources.py             # Adicionar fontes locais / Google Photos
│       ├── rules.py               # Destino, padrão, modo copy/move
│       ├── preview.py             # Treeview do plano de organização
│       ├── duplicates.py          # Detecção e revisão de duplicatas
│       ├── progress.py            # Barra de progresso, log em tempo real
│       └── report.py              # Relatório final, exportar HTML
│
├── gui/widgets/
│   ├── thumbnail_viewer.py        # Miniaturas com Pillow
│   ├── storage_chart.py           # Gráficos matplotlib (donut + barras)
│   └── file_tree.py               # Treeview customizado
│
├── integrations/
│   └── google_photos.py           # OAuth2 + download Google Photos
│
└── utils/
    ├── constants.py               # Extensões suportadas, caminhos, constantes
    └── formatting.py              # format_size, format_count, format_eta, format_speed
```

---

## Como funciona

### Pipeline de sessão

```
1. Fontes       → Define pastas de origem (local ou Google Photos)
2. Regras       → Define destino, padrão de pastas e modo (copy/move)
3. Preview      → plan_organization() calcula todas as operações sem executar nada
4. Duplicatas   → find_exact_duplicates() + find_visual_duplicates() nas fontes
5. Execução     → execute_plan() com ThreadPoolExecutor, pause/cancel em tempo real
6. Relatório    → Estatísticas, lista de erros, exportação HTML
```

### Índice de destino (cache SQLite)

Na primeira execução, o app varre e calcula SHA-256 de todos os arquivos já presentes na pasta destino, armazenando em `destination_index`. Nas execuções seguintes, apenas arquivos com `mtime` diferente são recomputados — tornando o planejamento ordens de magnitude mais rápido para coleções grandes.

### Detecção de duplicatas em 3 camadas

```
Tamanho → Partial SHA-256 (primeiros 64 KB) → Full SHA-256
```

Cada camada elimina falsos candidatos antes da próxima, minimizando leituras desnecessárias de disco.

### Execução paralela

`ThreadPoolExecutor` com workers configuráveis (1/2/4/8). I/O-bound — o GIL é liberado durante syscalls de disco. `shutil.copy2` usa `CopyFileEx` internamente no Windows para cópias eficientes.

---

## Banco de dados

SQLite com WAL mode em `%USERPROFILE%\.photovault\database.db`.

| Tabela | Conteúdo |
|---|---|
| `files` | Metadados e hashes de arquivos já scaneados (cache) |
| `sessions` | Histórico de execuções com estatísticas |
| `destination_index` | Índice cacheado da pasta destino por `(destination, path)` |

---

## Formatos suportados

**Fotos:** `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.tiff` `.tif` `.webp` `.heic` `.heif` `.raw` `.cr2` `.nef` `.arw` `.dng` `.orf` `.rw2` `.pef`

**Vídeos:** `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.webm` `.m4v` `.3gp` `.mts` `.m2ts`

---

## Padrões de organização

| Padrão | Exemplo de saída |
|---|---|
| `{year}/{month:02d}` | `2024/01/foto.jpg` |
| `{year}/{month_name}` | `2024/Janeiro/foto.jpg` |
| `{year}` | `2024/foto.jpg` |
| `{year}/{month:02d}/{day:02d}` | `2024/01/15/foto.jpg` |
| Sem data | `sem-data/foto.jpg` |

Colisões de nome são resolvidas automaticamente com sufixo `_001`, `_002`, etc.

---

## Tech stack

| Biblioteca | Uso |
|---|---|
| `customtkinter` | Interface moderna dark mode |
| `Pillow` | Miniaturas, leitura de imagens |
| `exifread` | Extração de data EXIF |
| `hachoir` | Metadados de vídeo |
| `imagehash` | pHash para duplicatas visuais |
| `matplotlib` | Gráficos do dashboard |
| `google-auth-oauthlib` | Integração Google Photos |
| `PyInstaller` | Geração do executável Windows |
| `SQLite` (stdlib) | Persistência local |

---

## Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
