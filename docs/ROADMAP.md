# Roadmap E Melhorias Propostas

Este roadmap organiza melhorias por prioridade pratica. A prioridade considera impacto no usuario, risco operacional e quanto a base atual ja prepara a funcionalidade.

## P0 - Base E Confiabilidade

### 1. Documentacao viva

Status: feito nesta revisao.

Entregas:

- README atualizado como porta de entrada;
- arquitetura detalhada em `docs/ARCHITECTURE.md`;
- roadmap em `docs/ROADMAP.md`;
- checklist de release em `docs/RELEASE.md`;
- diagramas de runtime, importacao, catalogo e metadados.

### 2. Checklist de release local

Problema: o projeto tem varios runtimes e o processo de build precisa ficar repetivel.

Status: documentado em `docs/RELEASE.md`.

Proposta:

- documentar sequencia: testes Python, teste TS, build frontend, cargo check, build Tauri debug/release;
- registrar onde o binario final aparece;
- incluir checagem de `.venv`, Node, Rust, ExifTool e ffmpeg.

### 3. Diagnostico de ambiente

Status: implementado no comando `diagnostics` e no painel Ambiente do Cockpit.

Problema: erros comuns hoje podem vir de Python sem pytest, PowerShell bloqueando `npm.ps1`, ExifTool ausente, Rust ausente ou `.venv` incompleta.

Implementado:

- retornar status de Python, dependencias, Node/npm, Cargo, ExifTool, ffmpeg, DB path, log path e permissoes basicas;
- exibir uma tela ou painel no Cockpit.

## P1 - Escala Da Galeria E Contratos

### 4. Paginacao ou virtualizacao da galeria

Status: curto prazo implementado no frontend com renderizacao incremental da grade. Ainda falta mover filtros/paginacao para SQLite.

Problema: `GALLERY_ITEM_LIMIT` chega a 50000 itens e a UI filtra localmente.

Implementado:

- renderizacao inicial limitada a 240 cards;
- botao para carregar mais resultados filtrados sem redesenhar todos os itens de uma vez.

Proximos passos:

- medio prazo: mover filtros/paginacao para SQLite;
- contrato sugerido: `gallery({ limit, offset, filter, sort })`;
- manter facetas agregadas independentes da pagina.

Impacto:

- melhor tempo de carregamento;
- menor memoria no frontend;
- base para galerias grandes.

### 5. Busca FTS5 real na UI

Status: implementado via `search_gallery`, `catalog_search` FTS5 e fallback `LIKE`.

Problema: `catalog_search` ja existe, mas a busca da UI ainda e local.

Implementado:

- usar `catalog_search MATCH ?` com fallback seguro para query simples;
- retornar resultados no formato da galeria;
- atualizar `refresh_catalog_search_conn` quando tags entram.

Impacto:

- busca mais rapida;
- busca por camera, lente, device, extensao, path e tags futuras.

### 6. Contratos TypeScript/Python mais explicitos

Status: parcialmente implementado com novos testes de bridge e banco para `state`, `search_gallery`, `diagnostics`, catalogo e saude.

Problema: os tipos do frontend sao manuais e podem divergir da bridge.

Proposta:

- documentar payloads/respostas em `docs/ARCHITECTURE.md`;
- adicionar testes de contrato para `state`, `gallery`, `import_insights` e `progress`;
- opcional: gerar JSON Schema a partir de dataclasses/Pydantic no futuro.

Impacto:

- menos regressao silenciosa;
- refactors mais seguros.

### 7. Jobs longos persistentes

Status: base de schema `background_jobs` e resumo `job_summary` implementados. Workers retomaveis completos ainda pendentes.

Problema: analise, ingestao, previews e ExifTool sao operacoes longas disparadas por chamadas bridge.

Proposta:

- modelar jobs no SQLite;
- rodar processamento em passos retomaveis;
- preservar progresso por job;
- permitir retry/cancelamento controlado.

Impacto:

- app mais resiliente;
- melhor experiencia em imports grandes;
- menos dependencia de uma chamada longa nao interrompida.

## P2 - Produto E Curadoria

### 8. Tela de Saude da Galeria

Status: implementado no Cockpit e no comando `health`.

Problema: existem sinais dispersos de risco operacional.

Proposta:

- painel com previews faltando, metadados pendentes, arquivos nao encontrados, itens sem data, videos grandes, duplicatas e erros recentes;
- acoes diretas: gerar previews, enriquecer metadados, localizar arquivo, filtrar problema.

Impacto:

- usuario sabe o que precisa cuidar;
- transforma sinais tecnicos em tarefas claras.

### 9. Tags e notas na UI

Status: implementado no inspetor da Galeria com `catalog`, `update_tags` e `add_note`.

Problema: tabelas `catalog_tags`, `asset_tags` e `catalog_notes` ja existem, mas ainda nao tem workflow.

Proposta:

- permitir tags manuais por asset;
- notas por item;
- filtro por tag;
- indexar tags/notas no `catalog_search`.

Impacto:

- curadoria real;
- base forte para agente/IA depois.

### 10. Persistencia de preferencias de UI

Status: implementado com `localStorage` para ultima view e filtros da galeria.

Problema: filtros e ultima view nao persistem.

Proposta:

- salvar filtros, view ativa e layout localmente;
- restaurar ao abrir;
- botao claro para limpar filtros.

Impacto:

- uso diario mais fluido;
- reduz repeticao.

### 11. Import resumivel

Status: parcialmente implementado. Operacoes `done/skipped` nao sao reexecutadas, e `health` lista imports retomaveis. Falta uma UX dedicada de continuar/cancelar por plano.

Problema: ingestao ja registra operacoes, mas o fluxo de retomar precisa ficar explicito.

Proposta:

- detectar planos incompletos;
- oferecer continuar, revisar ou cancelar;
- pular operacoes `done` e retentar `error/planned`;
- preservar metricas por tentativa.

Impacto:

- imports grandes ficam mais seguros;
- melhor recuperacao apos queda/fechamento.

## P3 - Inteligencia E Experiencias Avancadas

### 12. Agente de insights

Status: primeira fase implementada como insights deterministicas em `health`, sem modelo externo.

Problema: o catalogo ja esta preparado, mas nao chama modelos externos.

Proposta:

- primeira fase: consultas deterministicas geradas a partir de templates;
- segunda fase: agente com ferramentas limitadas para consultar SQLite;
- perguntas exemplo: "quais anos estao mais incompletos?", "quais cameras geraram videos mais pesados?", "quais itens precisam de metadados?".

Impacto:

- transforma catalogo em assistente de curadoria;
- alto valor quando a galeria crescer.

### 13. Mapa GPS

Status: dados GPS ja aparecem no inspetor e entram no catalogo quando extraidos. Visualizacao em mapa ainda pendente.

Problema: GPS ja pode ser promovido dos metadados, mas nao ha visualizacao.

Proposta:

- faceta "com localizacao";
- mapa local/web opcional;
- agrupamento por coordenadas aproximadas;
- cuidado com privacidade e exportacao.

Impacto:

- exploracao geografica da memoria fotografica.

### 14. Duplicatas visuais avancadas

Status: suporte auxiliar de perceptual hash permanece no core antigo; experiencia central de revisao visual ainda pendente.

Problema: o fluxo principal usa SHA-256 para identidade exata. Ha suporte auxiliar a perceptual hash, mas nao e experiencia central.

Proposta:

- job de similaridade visual;
- grupos de possiveis duplicatas;
- sugestao de keeper por qualidade/resolucao/metadados;
- revisao manual antes de qualquer acao destrutiva.

Impacto:

- reduz colecoes redundantes;
- precisa de UX conservadora.

### 15. Empacotamento release

Status: parcialmente implementado para release de teste em Windows.

Problema: o caminho debug funciona, mas release final precisa checklist e decisao de distribuicao.

Proposta:

- implementado: bridge Python empacotada como `photovault-bridge.exe` via PyInstaller para reduzir dependencia da `.venv` em outro dispositivo;
- implementado: `ffmpeg.exe`, `ffprobe.exe` e ExifTool entram como recursos do bundle de teste e sao passados para a bridge por variavel de ambiente;
- validar Tauri release em maquina Windows limpa;
- documentar instalador;
- automatizar release no GitHub depois que o fluxo local estiver estavel.
- eliminar a janela de console/cmd vazia que fica aberta ao fundo quando o frontend inicia no Windows.

Observacao de UX/runtime:

- implementado: o binario Tauri agora usa `windows_subsystem = "windows"` tambem em builds debug para evitar a janela de console vazia atras do frontend;
- o Tauri ja tenta iniciar a bridge Python com `CREATE_NO_WINDOW`;
- se ainda aparecer uma janela de cmd vazia, investigar processo auxiliar externo ao Tauri ou alguma execucao manual por terminal.

Impacto:

- app instalavel;
- base para compartilhar fora do ambiente dev.
- experiencia desktop mais limpa, sem terminal residual atras da janela principal.

### 16. UX da grade por proporcao real

Status: implementado na primeira versao com modos de grade `Preencher`, `Inteira` e `Compacta`.

Problema: os cards da Galeria hoje usam area visual quadrada/fechada, o que favorece consistencia da grade, mas pode cortar ou esconder composicao real. Fotos de camera costumam ser 4:3 ou 3:2; videos e drones frequentemente sao 16:9; celulares podem aparecer em 9:16; panoramas e exports tambem variam.

Proposta:

- implementado: modo `Inteira` usa `aspect-ratio` por item a partir de `resolution` e preserva a foto/video sem corte com `object-fit: contain`;
- implementado: modo `Preencher` mantem a experiencia compacta original com corte controlado;
- implementado: modo `Compacta` reduz densidade para varredura rapida;
- implementado: preferencia persistida no `localStorage`;
- proximo passo opcional: evoluir para masonry/timeline visual quando houver volume maior e mais metadados de dimensao.

Impacto:

- melhora avaliacao visual sem abrir item por item;
- evita que cortes do thumbnail escondam enquadramento real;
- deixa a galeria mais fiel para fotos de camera, drone e celular;
- cria base para modos futuros como masonry ou timeline visual.

### 17. UX dos filtros superiores da Galeria

Status: implementado com menu controlado.

Problema: os menus/dropdowns da barra superior de filtros da Galeria ficam presos abertos depois que o usuario seleciona uma opcao. Hoje e preciso clicar novamente no mesmo filtro para fechar, o que deixa a interacao pesada e pode cobrir a grade.

Proposta:

- implementado: dropdown fecha imediatamente depois da escolha;
- implementado: clique fora fecha o menu aberto;
- implementado: apenas um filtro fica aberto por vez;
- proximo passo opcional: refinar navegacao por teclado/ARIA para acessibilidade completa.

Impacto:

- deixa a busca/filtro mais fluida;
- evita dropdown preso sobre a galeria;
- aproxima o comportamento do padrao esperado de menus desktop.

### 18. Bug de enriquecimento de metadados no frontend

Status: correcao aplicada e validada em testes/build locais.

Problema: ao rodar o enriquecimento de metadados pelo frontend, a execucao termina, mas os metadados nao aparecem preenchidos na Galeria/Cockpit. O diagnostico atual mostra ExifTool disponivel e fila pendente, entao precisamos confirmar se a falha esta na execucao do backend, na promocao para `assets`/`metadata_extractions`, no refresh da galeria, no backfill, ou apenas na hidratacao/renderizacao dos campos no frontend.

Correcoes aplicadas:

- payload consolidado da Galeria passa a priorizar dados `exiftool/status ok` antes de valores antigos/backfill;
- `ffmpeg-ffprobe-static` foi incorporado ao desenvolvimento e `ffprobe` estatico e usado para videos quando disponivel;
- extracao de video promove duracao, dimensoes, codec, bitrate e frame rate;
- ainda monitorar refresh do frontend apos jobs longos e consistencia em bases ja populadas antes da correcao.

Proposta de investigacao:

- rodar `bridge.py enrich_metadata` com limite pequeno e capturar resultado;
- consultar `metadata_extractions` e `asset_processing_state` antes/depois;
- validar um asset especifico com `catalog/gallery` para ver se campos aparecem no payload JSON;
- exibir contadores de `enriched`, `skipped`, `errors`, `pending`, `ok` no painel de Saude;
- forcar refresh de galeria apos enriquecimento e limpar possiveis dados antigos;
- adicionar teste cobrindo promocao de um JSON realista de ExifTool ate o payload da Galeria.

Impacto:

- metadados ricos sao centrais para camera, lente, GPS, video, filtros e insights;
- sem isso, a Galeria fica com muitos campos `Desconhecido`;
- corrigir esse fluxo melhora imediatamente facetas, busca e Saude da Galeria.

### 19. Redesign do Cockpit

Status: primeira iteracao implementada.

Problema: o Cockpit ja mostra muitos sinais importantes, mas alguns blocos ainda parecem mais tecnicos do que didaticos. Os big numbers podem ser mais elegantes e uteis, a distribuicao de midia pode ser mais visual, e a inteligencia da galeria pode agrupar melhor os alertas/atalhos para orientar o usuario.

Proposta:

- implementado: big numbers e metric cards receberam acabamento visual mais claro e compacto;
- implementado: distribuicao de midia virou donut chart com total no centro e legenda clicavel;
- implementado: "Inteligencia da galeria" foi agrupada em categorias didaticas:
  - Qualidade do catalogo: sem data, metadados pendentes, previews faltando;
  - Armazenamento: videos grandes, RAWs pesados, extensoes que ocupam mais espaco;
  - Origem/captura: cameras, drones, celulares, apps;
  - Acoes recomendadas: enriquecer metadados, gerar previews, revisar imports;
- implementado: cards de insights continuam acionaveis e conectados aos filtros existentes;
- proximo passo opcional: deduplicar ainda mais "Risco operacional", "Saude" e "Inteligencia" conforme surgirem mais sinais reais;
- implementado: graficos pequenos e densos, sem cara de landing page: donut, barras compactas e listas priorizadas;
- implementado: clique direto para filtrar a Galeria a partir de cada insight;
- garantir que o layout continue escaneavel em telas menores.

Impacto:

- Cockpit vira uma tela de decisao, nao so um painel de numeros;
- melhora a leitura do acervo em poucos segundos;
- ajuda o usuario a entender o que fazer em seguida;
- deixa o produto mais polido e menos "debug dashboard".

## Ordem Recomendada

1. Checklist de release local.
2. Busca FTS5 real.
3. Contratos/testes bridge.
4. Jobs longos persistentes.
5. Saude da Galeria.
6. Tags/notas.
7. Import resumivel.
8. Agente de insights.
9. UX da grade por proporcao real.
10. UX dos filtros superiores da Galeria.
11. Bug de enriquecimento de metadados no frontend.
12. Redesign do Cockpit.

Essa ordem reduz risco tecnico antes de adicionar experiencias mais ambiciosas.
