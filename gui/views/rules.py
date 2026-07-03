import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.patterns import BUILTIN_PATTERNS, preview_pattern, validate_pattern
from gui.components import ghost_button, page_frame, page_header, primary_button, section
from gui.theme import (
    ACCENT,
    BORDER,
    ERROR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_HEADER,
    FONT_SIZE_SMALL,
    SUCCESS,
    SURFACE_ALT,
    TEXT,
    TEXT_MUTED,
    WARNING,
)
from utils.formatting import format_size


class RulesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        page_header(
            self.scroll,
            "Regras",
            "Defina destino, estrutura de pastas e segurancas antes do preview.",
        )

        dest_card = section(self.scroll, "Destino", "Pasta onde a biblioteca organizada sera criada.")
        dest_body = ctk.CTkFrame(dest_card, fg_color="transparent")
        dest_body.pack(fill="x", padx=18, pady=(0, 16))

        self.dest_var = ctk.StringVar(value=str(self.app.app_state.get("destination") or ""))
        self.dest_entry = ctk.CTkEntry(
            dest_body,
            textvariable=self.dest_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            placeholder_text="Selecione a pasta de destino...",
            height=40,
            fg_color=SURFACE_ALT,
            border_color=BORDER,
            text_color=TEXT,
        )
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ghost_button(dest_body, "Procurar", self._browse_dest, width=110, height=40).pack(side="right")

        self._space_panel = ctk.CTkFrame(dest_card, fg_color=SURFACE_ALT, corner_radius=8)
        space_inner = ctk.CTkFrame(self._space_panel, fg_color="transparent")
        space_inner.pack(fill="x", padx=14, pady=12)

        row = ctk.CTkFrame(space_inner, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        self._src_size_lbl = ctk.CTkLabel(row, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED)
        self._src_size_lbl.pack(side="left")
        self._free_lbl = ctk.CTkLabel(row, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED)
        self._free_lbl.pack(side="left", expand=True)
        self._space_status_lbl = ctk.CTkLabel(row, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        self._space_status_lbl.pack(side="right")

        bar_frame = ctk.CTkFrame(space_inner, fg_color="#0d131a", corner_radius=4, height=10)
        bar_frame.pack(fill="x")
        bar_frame.pack_propagate(False)
        self._bar_used = ctk.CTkFrame(bar_frame, fg_color="#475569", corner_radius=4, height=10)
        self._bar_used.place(relx=0, rely=0, relwidth=0, relheight=1)
        self._bar_add = ctk.CTkFrame(bar_frame, fg_color=ACCENT, corner_radius=0, height=10)
        self._bar_add.place(relx=0, rely=0, relwidth=0, relheight=1)

        pattern_card = section(self.scroll, "Organizacao", "Escolha a estrutura de subpastas.")
        pattern_body = ctk.CTkFrame(pattern_card, fg_color="transparent")
        pattern_body.pack(fill="x", padx=18, pady=(0, 16))

        pattern_options = [p["label"] for p in BUILTIN_PATTERNS] + ["Personalizado"]
        self.pattern_combo = ctk.CTkOptionMenu(
            pattern_body,
            values=pattern_options,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=SURFACE_ALT,
            button_color=ACCENT,
            button_hover_color=ACCENT,
            command=self._on_pattern_change,
            height=38,
        )
        self.pattern_combo.pack(anchor="w", pady=(0, 10))

        self.custom_pattern_var = ctk.StringVar(value=self.app.app_state.get("pattern", "{year}/{month:02d}"))
        self.custom_entry = ctk.CTkEntry(
            pattern_body,
            textvariable=self.custom_pattern_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            placeholder_text="{year}/{month:02d}",
            height=40,
            fg_color=SURFACE_ALT,
            border_color=BORDER,
            text_color=TEXT,
        )
        self.custom_entry.pack(fill="x")
        self.custom_entry.bind("<KeyRelease>", lambda _event: self._update_preview())

        self.preview_label = ctk.CTkLabel(
            pattern_body,
            text="Preview: ...",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=ACCENT,
            anchor="w",
        )
        self.preview_label.pack(anchor="w", pady=(8, 0))

        mode_card = section(self.scroll, "Modo", "Copiar preserva a origem; mover economiza uma etapa depois.")
        mode_body = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_body.pack(fill="x", padx=18, pady=(0, 16))
        self.mode_var = ctk.StringVar(value=self.app.app_state.get("mode", "copy"))
        self.mode_control = ctk.CTkSegmentedButton(
            mode_body,
            values=["copy", "move"],
            variable=self.mode_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE_ALT,
            unselected_hover_color="#22303d",
            height=34,
        )
        self.mode_control.pack(anchor="w")

        adv_card = section(self.scroll, "Seguranca", "Opcoes que evitam perda, duplicacao e ruido no resultado.")
        adv_body = ctk.CTkFrame(adv_card, fg_color="transparent")
        adv_body.pack(fill="x", padx=18, pady=(0, 16))

        self.include_no_date_var = ctk.BooleanVar(value=self.app.app_state.get("include_no_date", True))
        ctk.CTkCheckBox(
            adv_body,
            text='Incluir arquivos sem data em "sem-data"',
            variable=self.include_no_date_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT,
            fg_color=ACCENT,
            hover_color=ACCENT,
        ).pack(anchor="w", pady=4)

        self.skip_existing_var = ctk.BooleanVar(value=self.app.app_state.get("skip_existing", True))
        ctk.CTkCheckBox(
            adv_body,
            text="Pular arquivos que ja existem no destino por SHA-256",
            variable=self.skip_existing_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT,
            fg_color=ACCENT,
            hover_color=ACCENT,
        ).pack(anchor="w", pady=4)

        thresh = ctk.CTkFrame(adv_body, fg_color="transparent")
        thresh.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(
            thresh,
            text="Sensibilidade visual pHash",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT,
        ).pack(side="left")
        self.thresh_label = ctk.CTkLabel(
            thresh,
            text=str(self.app.app_state.get("phash_threshold", 10)),
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=ACCENT,
            width=32,
        )
        self.thresh_label.pack(side="right")

        self.thresh_slider = ctk.CTkSlider(
            adv_body,
            from_=0,
            to=20,
            number_of_steps=20,
            fg_color=SURFACE_ALT,
            progress_color=ACCENT,
            button_color=ACCENT,
            command=self._on_thresh_change,
        )
        self.thresh_slider.set(self.app.app_state.get("phash_threshold", 10))
        self.thresh_slider.pack(fill="x", pady=(8, 0))

        nav = ctk.CTkFrame(self.scroll, fg_color="transparent")
        nav.pack(fill="x", pady=(6, 0))
        primary_button(nav, "Gerar preview", self._continue, width=160, height=42).pack(side="right")

        self._set_pattern_from_state()
        self._update_preview()

    def _browse_dest(self):
        path = filedialog.askdirectory(title="Selecionar pasta de destino")
        if path:
            self.dest_var.set(path)
            self._check_space(Path(path))

    def _check_space(self, dest: Path):
        from core.scanner import get_drive_info

        sources = self.app.app_state.get("sources", [])
        src_bytes = sum(s.get("size_bytes", 0) for s in sources if s.get("type") != "cloud")

        self._space_panel.pack(fill="x", padx=18, pady=(0, 16))
        self._src_size_lbl.configure(text="Analisando disco...")
        self._free_lbl.configure(text="")
        self._space_status_lbl.configure(text="")

        def worker():
            info = get_drive_info(dest)
            self.scroll.after(0, lambda: self._update_space_panel(info, src_bytes))

        threading.Thread(target=worker, daemon=True).start()

    def _update_space_panel(self, info: dict, src_bytes: int):
        total = info.get("total_space", 0)
        used = info.get("used_space", 0)
        free = info.get("free_space", 0)

        if total == 0:
            self._src_size_lbl.configure(text="Disco nao detectado.")
            return

        used_ratio = used / total
        add_ratio = min(src_bytes / total, max(1 - used_ratio, 0))
        self._bar_used.place(relx=0, relwidth=used_ratio)
        self._bar_add.place(relx=used_ratio, relwidth=add_ratio)

        self._src_size_lbl.configure(
            text=f"Origem: {format_size(src_bytes)}" if src_bytes else "Origem: execute o scan para estimar"
        )
        self._free_lbl.configure(text=f"{format_size(used)} usados de {format_size(total)}")

        if src_bytes == 0:
            self._space_status_lbl.configure(text="Scan pendente", text_color=WARNING)
            self._bar_add.configure(fg_color=WARNING)
        elif src_bytes > free:
            self._space_status_lbl.configure(text=f"Faltam {format_size(src_bytes - free)}", text_color=ERROR)
            self._bar_add.configure(fg_color=ERROR)
        elif src_bytes > free * 0.8:
            self._space_status_lbl.configure(text=f"Espaco apertado: {format_size(free)} livres", text_color=WARNING)
            self._bar_add.configure(fg_color=WARNING)
        else:
            self._space_status_lbl.configure(text=f"Espaco suficiente: {format_size(free)} livres", text_color=SUCCESS)
            self._bar_add.configure(fg_color=SUCCESS)

    def _on_pattern_change(self, value: str):
        for p in BUILTIN_PATTERNS:
            if p["label"] == value:
                self.custom_pattern_var.set(p["pattern"])
                self.custom_entry.configure(state="disabled")
                break
        else:
            self.custom_entry.configure(state="normal")
        self._update_preview()

    def _set_pattern_from_state(self):
        pat = self.app.app_state.get("pattern", "{year}/{month:02d}")
        self.custom_pattern_var.set(pat)
        for p in BUILTIN_PATTERNS:
            if p["pattern"] == pat:
                self.pattern_combo.set(p["label"])
                self.custom_entry.configure(state="disabled")
                return
        self.pattern_combo.set("Personalizado")

    def _update_preview(self):
        pat = self.custom_pattern_var.get()
        if validate_pattern(pat):
            self.preview_label.configure(text=f"Preview: {preview_pattern(pat)}", text_color=ACCENT)
        else:
            self.preview_label.configure(text="Padrao invalido", text_color=ERROR)

    def _on_thresh_change(self, val):
        self.thresh_label.configure(text=str(int(val)))

    def _continue(self):
        dest = self.dest_var.get().strip()
        if not dest:
            self.dest_entry.configure(border_color=ERROR)
            return
        self.dest_entry.configure(border_color=BORDER)

        pat = self.custom_pattern_var.get()
        if not validate_pattern(pat):
            return

        self.app.app_state["destination"] = Path(dest)
        self.app.app_state["pattern"] = pat
        self.app.app_state["mode"] = self.mode_var.get()
        self.app.app_state["phash_threshold"] = int(self.thresh_slider.get())
        self.app.app_state["include_no_date"] = self.include_no_date_var.get()
        self.app.app_state["skip_existing"] = self.skip_existing_var.get()
        self.app.app_state["plan"] = None

        self.main_window.navigate("preview")

    def refresh(self):
        self._set_pattern_from_state()
        self._update_preview()
        dest = self.app.app_state.get("destination")
        if dest:
            self.dest_var.set(str(dest))
            self._check_space(dest)
