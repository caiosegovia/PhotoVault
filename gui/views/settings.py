import shutil
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui.components import ghost_button, page_frame, page_header, primary_button, section
from gui.theme import (
    ACCENT,
    BORDER,
    ERROR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    SUCCESS,
    SURFACE_ALT,
    TEXT,
    TEXT_MUTED,
    WARNING,
)
from utils.constants import CONFIG_DIR, TOKEN_PATH


class SettingsView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        page_header(
            self.scroll,
            "Ajustes",
            "Configure credenciais opcionais e conexoes externas.",
        )
        self._build_google_section()

    def _build_google_section(self):
        card = section(
            self.scroll,
            "Google Photos",
            "Use OAuth2 para incluir fotos e videos da sua conta como fonte.",
        )

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(0, 16))

        cred_row = self._status_row(body, "Credenciais OAuth2")
        self.cred_status = ctk.CTkLabel(
            cred_row,
            text=self._cred_status_text(),
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=SUCCESS if self._cred_path().exists() else TEXT_MUTED,
            anchor="w",
        )
        self.cred_status.pack(anchor="w", pady=(3, 10))
        primary_button(
            cred_row,
            "Selecionar client_secret.json",
            self._browse_credentials,
            width=230,
            height=34,
        ).pack(anchor="w")

        auth_row = self._status_row(body, "Conta")
        self.auth_status = ctk.CTkLabel(
            auth_row,
            text=self._auth_status_text(),
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=SUCCESS if TOKEN_PATH.exists() else TEXT_MUTED,
            anchor="w",
        )
        self.auth_status.pack(anchor="w", pady=(3, 10))

        btns = ctk.CTkFrame(auth_row, fg_color="transparent")
        btns.pack(anchor="w")
        self.connect_btn = primary_button(btns, "Conectar", self._connect_google, width=120, height=34)
        self.connect_btn.pack(side="left", padx=(0, 8))
        ghost_button(btns, "Desconectar", self._disconnect_google, width=120, height=34).pack(side="left")

    def _status_row(self, parent, title: str):
        row = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        row.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(
            inner,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        return inner

    def _cred_path(self) -> Path:
        return CONFIG_DIR / "google_client_secret.json"

    def _cred_status_text(self) -> str:
        p = self._cred_path()
        if p.exists():
            return f"Configurado: {p}"
        assets = Path("assets") / "google_client_secret.json"
        if assets.exists():
            return f"Configurado: {assets}"
        return "Nenhum arquivo de credenciais configurado."

    def _auth_status_text(self) -> str:
        client = self.app.app_state.get("google_client")
        if client:
            return "Conta conectada nesta sessao."
        if TOKEN_PATH.exists():
            return "Token salvo. Sera usado ao adicionar Google Photos."
        return "Nao autenticado."

    def _browse_credentials(self):
        path = filedialog.askopenfilename(
            title="Selecionar client_secret.json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, self._cred_path())
        self.cred_status.configure(text=f"Copiado para {self._cred_path()}", text_color=SUCCESS)

    def _connect_google(self):
        cred_path = self._cred_path()
        if not cred_path.exists():
            assets = Path("assets") / "google_client_secret.json"
            if assets.exists():
                cred_path = assets
            else:
                self.auth_status.configure(text="Configure o arquivo de credenciais primeiro.", text_color=ERROR)
                return

        self.connect_btn.configure(state="disabled", text="Abrindo...")
        self.auth_status.configure(text="Aguardando autenticacao no navegador...", text_color=WARNING)

        def worker():
            try:
                from integrations.google_photos import GooglePhotosClient

                client = GooglePhotosClient(str(cred_path))
                success = client.authenticate()
                if success:
                    self.app.app_state["google_client"] = client
                    self.parent.after(0, lambda: self._on_auth_done(True))
                else:
                    self.parent.after(0, lambda: self._on_auth_done(False))
            except Exception as e:
                self.parent.after(0, lambda msg=str(e): self._on_auth_done(False, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_auth_done(self, success: bool, error: str = ""):
        self.connect_btn.configure(state="normal", text="Conectar")
        if success:
            self.auth_status.configure(text="Conta Google conectada com sucesso.", text_color=SUCCESS)
        else:
            msg = f"Falha na autenticacao{': ' + error if error else '.'}"
            self.auth_status.configure(text=msg, text_color=ERROR)

    def _disconnect_google(self):
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
        self.app.app_state["google_client"] = None
        self.auth_status.configure(text="Nao autenticado.", text_color=TEXT_MUTED)

    def refresh(self):
        self.cred_status.configure(
            text=self._cred_status_text(),
            text_color=SUCCESS if self._cred_path().exists() else TEXT_MUTED,
        )
        self.auth_status.configure(
            text=self._auth_status_text(),
            text_color=SUCCESS if (self.app.app_state.get("google_client") or TOKEN_PATH.exists()) else TEXT_MUTED,
        )
