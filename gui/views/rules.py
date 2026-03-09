import threading
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_BORDER,
                     COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
                     FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from core.patterns import BUILTIN_PATTERNS, preview_pattern, validate_pattern
from utils.formatting import format_size


class RulesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            self.scroll, text='Regras de Organização',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 20))

        # Destination
        dest_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        dest_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            dest_card, text='Pasta de Destino',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        dest_row = ctk.CTkFrame(dest_card, fg_color='transparent')
        dest_row.pack(fill='x', padx=20, pady=(0, 16))

        self.dest_var = ctk.StringVar(value=str(self.app.app_state.get('destination') or ''))
        self.dest_entry = ctk.CTkEntry(
            dest_row, textvariable=self.dest_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY), placeholder_text='Selecione a pasta de destino...',
            height=38
        )
        self.dest_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ctk.CTkButton(
            dest_row, text='Procurar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=100, height=38,
            command=self._browse_dest
        ).pack(side='right')

        # Space validation panel (hidden until destination is set)
        self._space_panel = ctk.CTkFrame(dest_card, fg_color='#0a2a50', corner_radius=8)
        # packed dynamically in _check_space

        space_inner = ctk.CTkFrame(self._space_panel, fg_color='transparent')
        space_inner.pack(fill='x', padx=14, pady=10)

        # Labels row
        labels_row = ctk.CTkFrame(space_inner, fg_color='transparent')
        labels_row.pack(fill='x', pady=(0, 6))

        self._src_size_lbl = ctk.CTkLabel(
            labels_row, text='',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM, anchor='w'
        )
        self._src_size_lbl.pack(side='left')

        self._space_status_lbl = ctk.CTkLabel(
            labels_row, text='',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), anchor='e'
        )
        self._space_status_lbl.pack(side='right')

        self._free_lbl = ctk.CTkLabel(
            labels_row, text='',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM, anchor='center'
        )
        self._free_lbl.pack(side='left', expand=True)

        # Capacity bar (stacked: used | will-add | free)
        bar_frame = ctk.CTkFrame(space_inner, fg_color='#1a1a3a', corner_radius=4, height=12)
        bar_frame.pack(fill='x')
        bar_frame.pack_propagate(False)
        self._bar_used = ctk.CTkFrame(bar_frame, fg_color='#2a5a8a', corner_radius=4, height=12)
        self._bar_used.place(relx=0, rely=0, relwidth=0, relheight=1)
        self._bar_add = ctk.CTkFrame(bar_frame, fg_color=COLOR_ACCENT, corner_radius=0, height=12)
        self._bar_add.place(relx=0, rely=0, relwidth=0, relheight=1)

        # Pattern selection
        pattern_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        pattern_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            pattern_card, text='Padrão de Subpastas',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        pattern_options = [p['label'] for p in BUILTIN_PATTERNS] + ['Personalizado']
        self.pattern_combo = ctk.CTkOptionMenu(
            pattern_card, values=pattern_options,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_CARD, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT2,
            command=self._on_pattern_change
        )
        self.pattern_combo.pack(anchor='w', padx=20, pady=(0, 8))

        self.custom_pattern_var = ctk.StringVar(value=self.app.app_state.get('pattern', '{year}/{month:02d}'))
        self.custom_entry = ctk.CTkEntry(
            pattern_card, textvariable=self.custom_pattern_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            placeholder_text='{year}/{month:02d}',
            height=38
        )
        self.custom_entry.pack(fill='x', padx=20, pady=(0, 8))
        self.custom_entry.bind('<KeyRelease>', lambda e: self._update_preview())

        self.preview_label = ctk.CTkLabel(
            pattern_card, text='Preview: ...',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_ACCENT2
        )
        self.preview_label.pack(anchor='w', padx=20, pady=(0, 16))

        # Set initial pattern
        self._set_pattern_from_state()
        self._update_preview()

        # Mode selection
        mode_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        mode_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            mode_card, text='Modo de Operação',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        self.mode_var = ctk.StringVar(value=self.app.app_state.get('mode', 'copy'))
        mode_frame = ctk.CTkFrame(mode_card, fg_color='transparent')
        mode_frame.pack(anchor='w', padx=20, pady=(0, 16))

        ctk.CTkRadioButton(
            mode_frame, text='Copiar arquivos (mais seguro)',
            variable=self.mode_var, value='copy',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT,
            fg_color=COLOR_ACCENT
        ).pack(side='left', padx=(0, 20))

        ctk.CTkRadioButton(
            mode_frame, text='Mover arquivos',
            variable=self.mode_var, value='move',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT,
            fg_color=COLOR_ACCENT
        ).pack(side='left')

        # Advanced options
        adv_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        adv_card.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(
            adv_card, text='Opções Avançadas',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', padx=20, pady=(16, 8))

        self.include_no_date_var = ctk.BooleanVar(
            value=self.app.app_state.get('include_no_date', True)
        )
        ctk.CTkCheckBox(
            adv_card, text='Incluir arquivos sem data (pasta "sem-data")',
            variable=self.include_no_date_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT,
            fg_color=COLOR_ACCENT
        ).pack(anchor='w', padx=20, pady=4)

        self.skip_existing_var = ctk.BooleanVar(
            value=self.app.app_state.get('skip_existing', True)
        )
        ctk.CTkCheckBox(
            adv_card,
            text='Evitar duplicatas no destino — pular arquivos já existentes (SHA-256)',
            variable=self.skip_existing_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT,
            fg_color=COLOR_ACCENT
        ).pack(anchor='w', padx=20, pady=(0, 4))

        # pHash threshold
        thresh_frame = ctk.CTkFrame(adv_card, fg_color='transparent')
        thresh_frame.pack(fill='x', padx=20, pady=(8, 0))

        ctk.CTkLabel(
            thresh_frame, text='Threshold pHash (similaridade visual):',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT
        ).pack(side='left')

        self.thresh_label = ctk.CTkLabel(
            thresh_frame, text=str(self.app.app_state.get('phash_threshold', 10)),
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_ACCENT2, width=30
        )
        self.thresh_label.pack(side='right')

        self.thresh_slider = ctk.CTkSlider(
            adv_card, from_=0, to=20, number_of_steps=20,
            fg_color=COLOR_BORDER, progress_color=COLOR_ACCENT,
            button_color=COLOR_ACCENT2,
            command=self._on_thresh_change
        )
        self.thresh_slider.set(self.app.app_state.get('phash_threshold', 10))
        self.thresh_slider.pack(fill='x', padx=20, pady=(4, 16))

        # Continue button
        ctk.CTkButton(
            self.scroll, text='Continuar → Preview',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, height=44, width=220,
            command=self._continue
        ).pack(pady=20)

    def _browse_dest(self):
        path = filedialog.askdirectory(title='Selecionar pasta de destino')
        if path:
            self.dest_var.set(path)
            self._check_space(Path(path))

    def _check_space(self, dest: Path):
        """Show source-size vs free-space validation panel."""
        from core.scanner import get_drive_info

        # Source size: sum across all local sources already scanned
        sources = self.app.app_state.get('sources', [])
        src_bytes = sum(s.get('size_bytes', 0) for s in sources
                        if s.get('type') != 'cloud')

        self._space_panel.pack(fill='x', padx=20, pady=(0, 14))
        self._src_size_lbl.configure(text='Analisando disco...')
        self._free_lbl.configure(text='')
        self._space_status_lbl.configure(text='')

        def worker():
            info = get_drive_info(dest)
            self.scroll.after(0, lambda: self._update_space_panel(info, src_bytes))

        threading.Thread(target=worker, daemon=True).start()

    def _update_space_panel(self, info: dict, src_bytes: int):
        total = info.get('total_space', 0)
        used = info.get('used_space', 0)
        free = info.get('free_space', 0)

        if total == 0:
            self._src_size_lbl.configure(text='Disco não detectado.')
            return

        used_ratio = used / total
        add_ratio = min(src_bytes / total, 1 - used_ratio)
        projected_used = used + src_bytes

        # Update bar positions
        self._bar_used.place(relx=0, relwidth=used_ratio)
        self._bar_add.place(relx=used_ratio, relwidth=add_ratio)

        # Labels
        src_txt = f'📦 Origem: {format_size(src_bytes)}' if src_bytes else '📦 Origem: tamanho desconhecido (execute o scan)'
        self._src_size_lbl.configure(text=src_txt)
        self._free_lbl.configure(
            text=f'💽 {format_size(used)} usados de {format_size(total)}'
        )

        # Status
        if src_bytes == 0:
            self._space_status_lbl.configure(
                text='⚠ Execute o scan das fontes', text_color=COLOR_WARNING
            )
            self._bar_add.configure(fg_color=COLOR_WARNING)
        elif src_bytes > free:
            falta = src_bytes - free
            self._space_status_lbl.configure(
                text=f'✗ Espaço insuficiente  (faltam {format_size(falta)})',
                text_color=COLOR_ERROR
            )
            self._bar_add.configure(fg_color=COLOR_ERROR)
        elif src_bytes > free * 0.8:
            self._space_status_lbl.configure(
                text=f'⚠ Espaço apertado  ({format_size(free)} livres)',
                text_color=COLOR_WARNING
            )
            self._bar_add.configure(fg_color=COLOR_WARNING)
        else:
            self._space_status_lbl.configure(
                text=f'✓ Espaço suficiente  ({format_size(free)} livres)',
                text_color=COLOR_SUCCESS
            )
            self._bar_add.configure(fg_color=COLOR_SUCCESS)

    def _on_pattern_change(self, value: str):
        for p in BUILTIN_PATTERNS:
            if p['label'] == value:
                self.custom_pattern_var.set(p['pattern'])
                self.custom_entry.configure(state='disabled')
                break
        else:
            self.custom_entry.configure(state='normal')
        self._update_preview()

    def _set_pattern_from_state(self):
        pat = self.app.app_state.get('pattern', '{year}/{month:02d}')
        self.custom_pattern_var.set(pat)
        for p in BUILTIN_PATTERNS:
            if p['pattern'] == pat:
                self.pattern_combo.set(p['label'])
                self.custom_entry.configure(state='disabled')
                return
        self.pattern_combo.set('Personalizado')

    def _update_preview(self):
        pat = self.custom_pattern_var.get()
        if validate_pattern(pat):
            prev = preview_pattern(pat)
            self.preview_label.configure(text=f'Preview: {prev}', text_color=COLOR_ACCENT2)
        else:
            self.preview_label.configure(text='Padrão inválido!', text_color='#e74c3c')

    def _on_thresh_change(self, val):
        v = int(val)
        self.thresh_label.configure(text=str(v))

    def _continue(self):
        dest = self.dest_var.get().strip()
        if not dest:
            self.dest_entry.configure(border_color='red')
            return
        self.dest_entry.configure(border_color=COLOR_BORDER)

        pat = self.custom_pattern_var.get()
        if not validate_pattern(pat):
            return

        self.app.app_state['destination'] = Path(dest)
        self.app.app_state['pattern'] = pat
        self.app.app_state['mode'] = self.mode_var.get()
        self.app.app_state['phash_threshold'] = int(self.thresh_slider.get())
        self.app.app_state['include_no_date'] = self.include_no_date_var.get()
        self.app.app_state['skip_existing'] = self.skip_existing_var.get()
        # Invalidate plan so Preview is forced to regenerate with new settings
        self.app.app_state['plan'] = None

        self.main_window.navigate('preview')

    def refresh(self):
        self._set_pattern_from_state()
        self._update_preview()
        dest = self.app.app_state.get('destination')
        if dest:
            self.dest_var.set(str(dest))
            self._check_space(dest)
