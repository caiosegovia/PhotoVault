import threading
import shutil
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.constants import CONFIG_DIR, TOKEN_PATH
from utils.formatting import format_size


class SettingsView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            self.scroll, text='Configurações',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 20))

        self._build_google_section()

    def _build_google_section(self):
        card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        card.pack(fill='x', pady=(0, 16))

        # Header
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(16, 4))
        ctk.CTkLabel(
            header, text='☁  Google Photos',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left')

        ctk.CTkLabel(
            card,
            text='Conecte sua conta Google para incluir o Google Photos como fonte de mídia.\n'
                 'Você precisará de um arquivo client_secret.json do Google Cloud Console.',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            justify='left', anchor='w'
        ).pack(anchor='w', padx=20, pady=(0, 14))

        # Credentials file row
        cred_row = ctk.CTkFrame(card, fg_color='#0a2a50', corner_radius=8)
        cred_row.pack(fill='x', padx=20, pady=(0, 10))

        cred_inner = ctk.CTkFrame(cred_row, fg_color='transparent')
        cred_inner.pack(fill='x', padx=14, pady=10)

        ctk.CTkLabel(
            cred_inner, text='Credenciais OAuth2',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_TEXT_DIM
        ).pack(anchor='w')

        self.cred_status = ctk.CTkLabel(
            cred_inner, text=self._cred_status_text(),
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=COLOR_SUCCESS if self._cred_path().exists() else COLOR_TEXT_DIM,
            anchor='w'
        )
        self.cred_status.pack(anchor='w', pady=(2, 6))

        ctk.CTkButton(
            cred_inner, text='Selecionar client_secret.json',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, height=32, width=240,
            command=self._browse_credentials
        ).pack(anchor='w')

        # Auth status row
        auth_row = ctk.CTkFrame(card, fg_color='#0a2a50', corner_radius=8)
        auth_row.pack(fill='x', padx=20, pady=(0, 16))

        auth_inner = ctk.CTkFrame(auth_row, fg_color='transparent')
        auth_inner.pack(fill='x', padx=14, pady=10)

        ctk.CTkLabel(
            auth_inner, text='Status da Conta',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_TEXT_DIM
        ).pack(anchor='w')

        self.auth_status = ctk.CTkLabel(
            auth_inner, text=self._auth_status_text(),
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=COLOR_SUCCESS if TOKEN_PATH.exists() else COLOR_TEXT_DIM,
            anchor='w'
        )
        self.auth_status.pack(anchor='w', pady=(2, 8))

        btn_row = ctk.CTkFrame(auth_inner, fg_color='transparent')
        btn_row.pack(anchor='w')

        self.connect_btn = ctk.CTkButton(
            btn_row, text='Conectar via Navegador',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_SUCCESS, hover_color='#27ae60',
            corner_radius=8, height=34, width=200,
            command=self._connect_google
        )
        self.connect_btn.pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            btn_row, text='Desconectar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_ERROR,
            border_color=COLOR_ERROR, border_width=1,
            corner_radius=8, height=34, width=120,
            command=self._disconnect_google
        ).pack(side='left')

    # ── helpers ──────────────────────────────────────────────────────────

    def _cred_path(self) -> Path:
        return CONFIG_DIR / 'google_client_secret.json'

    def _cred_status_text(self) -> str:
        p = self._cred_path()
        if p.exists():
            return f'✓  {p}'
        assets = Path('assets') / 'google_client_secret.json'
        if assets.exists():
            return f'✓  {assets}'
        return '✗  Nenhum arquivo de credenciais configurado.'

    def _auth_status_text(self) -> str:
        client = self.app.app_state.get('google_client')
        if client:
            return '✓  Conta conectada e autenticada nesta sessão'
        if TOKEN_PATH.exists():
            return '✓  Token salvo — será carregado automaticamente ao adicionar a fonte'
        return '✗  Não autenticado'

    # ── actions ──────────────────────────────────────────────────────────

    def _browse_credentials(self):
        path = filedialog.askopenfilename(
            title='Selecionar client_secret.json',
            filetypes=[('JSON', '*.json'), ('Todos', '*.*')]
        )
        if not path:
            return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, self._cred_path())
        self.cred_status.configure(
            text=f'✓  Copiado para {self._cred_path()}',
            text_color=COLOR_SUCCESS
        )

    def _connect_google(self):
        cred_path = self._cred_path()
        if not cred_path.exists():
            assets = Path('assets') / 'google_client_secret.json'
            if assets.exists():
                cred_path = assets
            else:
                self.auth_status.configure(
                    text='✗  Configure o arquivo de credenciais primeiro.',
                    text_color=COLOR_ERROR
                )
                return

        self.connect_btn.configure(state='disabled', text='Abrindo navegador...')
        self.auth_status.configure(
            text='Aguardando autenticação no navegador...',
            text_color=COLOR_WARNING
        )

        def worker():
            try:
                from integrations.google_photos import GooglePhotosClient
                client = GooglePhotosClient(str(cred_path))
                success = client.authenticate()
                if success:
                    self.app.app_state['google_client'] = client
                    self.parent.after(0, lambda: self._on_auth_done(True))
                else:
                    self.parent.after(0, lambda: self._on_auth_done(False))
            except Exception as e:
                self.parent.after(0, lambda msg=str(e): self._on_auth_done(False, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_auth_done(self, success: bool, error: str = ''):
        self.connect_btn.configure(state='normal', text='Conectar via Navegador')
        if success:
            self.auth_status.configure(
                text='✓  Conta Google conectada com sucesso!',
                text_color=COLOR_SUCCESS
            )
        else:
            msg = f'✗  Falha na autenticação{": " + error if error else "."}'
            self.auth_status.configure(text=msg, text_color=COLOR_ERROR)

    def _disconnect_google(self):
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
        self.app.app_state['google_client'] = None
        self.auth_status.configure(
            text='✗  Não autenticado',
            text_color=COLOR_TEXT_DIM
        )

    def refresh(self):
        self.cred_status.configure(
            text=self._cred_status_text(),
            text_color=COLOR_SUCCESS if self._cred_path().exists() else COLOR_TEXT_DIM
        )
        self.auth_status.configure(
            text=self._auth_status_text(),
            text_color=COLOR_SUCCESS if (self.app.app_state.get('google_client') or TOKEN_PATH.exists()) else COLOR_TEXT_DIM
        )
