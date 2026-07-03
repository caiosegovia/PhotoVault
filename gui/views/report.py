import os
import customtkinter as ctk
from pathlib import Path
from datetime import datetime
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count


class ReportView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        # Header
        header = ctk.CTkFrame(self.scroll, fg_color='transparent')
        header.pack(fill='x', pady=(0, 20))

        ctk.CTkLabel(
            header, text='Relatório Final',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left')

        btn_row = ctk.CTkFrame(header, fg_color='transparent')
        btn_row.pack(side='right')

        ctk.CTkButton(
            btn_row, text='Exportar HTML',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=140, height=36,
            command=self._export_html
        ).pack(side='left', padx=(0, 10))

        self.open_dest_btn = ctk.CTkButton(
            btn_row, text='Abrir Destino',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1,
            corner_radius=8, width=140, height=36,
            command=self._open_destination
        )
        self.open_dest_btn.pack(side='left')

        # Summary cards
        self.cards_frame = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self.cards_frame.pack(fill='x', pady=(0, 16))

        for i in range(4):
            self.cards_frame.columnconfigure(i, weight=1, uniform='rcard')

        self.card_processed = self._stat_card(0, 'Processados', '0', '✓', COLOR_SUCCESS)
        self.card_errors = self._stat_card(1, 'Erros', '0', '✕', COLOR_ERROR)
        self.card_dups = self._stat_card(2, 'Duplicatas', '0', '⧉', COLOR_WARNING)
        self.card_freed = self._stat_card(3, 'Liberado', '0 B', '♻', COLOR_ACCENT2)

        # Error list
        self.errors_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        self.errors_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            self.errors_card, text='Erros de Processamento',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        self.errors_list = ctk.CTkScrollableFrame(
            self.errors_card, fg_color='transparent', height=150
        )
        self.errors_list.pack(fill='x', padx=10, pady=(0, 16))

        # Details
        details_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        details_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            details_card, text='Detalhes da Sessão',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        self.details_text = ctk.CTkTextbox(
            details_card, height=150,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color='#111122', text_color=COLOR_TEXT, corner_radius=8
        )
        self.details_text.pack(fill='x', padx=10, pady=(0, 16))

    def _stat_card(self, col: int, title: str, value: str, icon: str, color: str):
        card = ctk.CTkFrame(self.cards_frame, fg_color=COLOR_CARD, corner_radius=12)
        card.grid(row=0, column=col, padx=8, pady=4, sticky='ew')
        ctk.CTkLabel(card, text=icon, font=(FONT_FAMILY, 24)).pack(pady=(16, 4))
        lbl = ctk.CTkLabel(card, text=value, font=(FONT_FAMILY, 20, 'bold'), text_color=color)
        lbl.pack()
        ctk.CTkLabel(card, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=COLOR_TEXT_DIM).pack(pady=(2, 16))
        return lbl

    def refresh(self):
        result = self.app.app_state.get('exec_result')
        dup = self.app.app_state.get('dup_result')

        if result:
            self.card_processed.configure(text=format_count(result.processed))
            self.card_errors.configure(text=format_count(result.errors))

            # Populate errors
            for w in self.errors_list.winfo_children():
                w.destroy()

            error_ops = [op for op in result.operations if op.status == 'error']
            if error_ops:
                for op in error_ops[:50]:
                    row = ctk.CTkFrame(self.errors_list, fg_color='transparent')
                    row.pack(fill='x', pady=2)
                    ctk.CTkLabel(
                        row, text=f'✕ {op.src.name}: {op.error}',
                        font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_ERROR, anchor='w'
                    ).pack(side='left')
            else:
                ctk.CTkLabel(
                    self.errors_list, text='Nenhum erro.',
                    text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_SMALL)
                ).pack(pady=10)

        if dup:
            dup_count = len(dup.exact) + len(dup.visual)
            self.card_dups.configure(text=format_count(dup_count))
            self.card_freed.configure(text=format_size(dup.space_wasted))

        # Details
        self.details_text.configure(state='normal')
        self.details_text.delete('1.0', 'end')
        sources = self.app.app_state.get('sources', [])
        dest = self.app.app_state.get('destination')
        pattern = self.app.app_state.get('pattern')
        mode = self.app.app_state.get('mode')

        self.details_text.insert('end', f'Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}\n')
        self.details_text.insert('end', f'Modo: {mode}\n')
        self.details_text.insert('end', f'Padrão: {pattern}\n')
        self.details_text.insert('end', f'Destino: {dest}\n')
        self.details_text.insert('end', f'Fontes: {len(sources)}\n')
        for s in sources:
            self.details_text.insert('end', f'  • {s["path"]}\n')
        self.details_text.configure(state='disabled')

    def _export_html(self):
        result = self.app.app_state.get('exec_result')
        dup = self.app.app_state.get('dup_result')
        dest = self.app.app_state.get('destination', Path.home())

        html = self._build_html(result, dup)
        report_path = dest / f'photovault_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html' if dest else Path.home() / 'photovault_report.html'

        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(html, encoding='utf-8')
            self._open_file(str(report_path))
        except Exception as e:
            pass

    def _build_html(self, result, dup) -> str:
        processed = result.processed if result else 0
        errors = result.errors if result else 0
        dup_count = len(dup.exact) + len(dup.visual) if dup else 0
        freed = format_size(dup.space_wasted) if dup else '0 B'

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>PhotoVault - Relatório</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #0b0b0d; color: #f4f4f5; padding: 40px; }}
h1 {{ color: #ef4444; }} h2 {{ color: #ef4444; border-bottom: 1px solid #303035; padding-bottom: 8px; }}
.card {{ background: #18181b; border: 1px solid #303035; border-radius: 8px; padding: 20px; margin: 10px 0; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
.stat {{ text-align: center; }}
.stat .value {{ font-size: 2em; font-weight: bold; color: #ef4444; }}
.stat .label {{ color: #a1a1aa; font-size: 0.9em; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #242428; padding: 10px; text-align: left; }}
td {{ padding: 8px; border-bottom: 1px solid #303035; }}
</style>
</head>
<body>
<h1>PhotoVault — Relatório de Organização</h1>
<p>Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
<div class="grid card">
  <div class="stat"><div class="value">{format_count(processed)}</div><div class="label">Processados</div></div>
  <div class="stat"><div class="value">{format_count(errors)}</div><div class="label">Erros</div></div>
  <div class="stat"><div class="value">{format_count(dup_count)}</div><div class="label">Duplicatas</div></div>
  <div class="stat"><div class="value">{freed}</div><div class="label">Liberado</div></div>
</div>
<h2>Configuração</h2>
<div class="card">
  <p><strong>Destino:</strong> {self.app.app_state.get('destination', '—')}</p>
  <p><strong>Padrão:</strong> {self.app.app_state.get('pattern', '—')}</p>
  <p><strong>Modo:</strong> {self.app.app_state.get('mode', '—')}</p>
</div>
</body>
</html>"""

    def _open_destination(self):
        dest = self.app.app_state.get('destination')
        if dest and Path(dest).exists():
            self._open_file(str(dest))

    def _open_file(self, path: str):
        import platform
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
