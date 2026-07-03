import customtkinter as ctk

from gui.app import PhotoVaultApp
from gui.theme import (
    ACCENT,
    APP_BG,
    BORDER,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    SIDEBAR_BG,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    TEXT_MUTED,
)
from utils.formatting import format_count


NAV_ITEMS = [
    ("organize", "Galeria"),
    ("vault", "Explorar"),
    ("report", "Auditoria"),
    ("settings", "Ajustes"),
]


class MainWindow:
    def __init__(self, app: PhotoVaultApp):
        self.app = app
        self.current_view = None
        self.views: dict = {}
        self.nav_buttons: dict = {}
        self.dup_badge_var = ctk.StringVar(value="")
        self.summary_var = ctk.StringVar(value="Nenhuma sessao configurada")
        self.step_var = ctk.StringVar(value="")

        self._build_layout()
        self._load_views()
        self.navigate("organize")

    def _build_layout(self):
        self.sidebar = ctk.CTkFrame(self.app, width=188, corner_radius=0, fg_color=SIDEBAR_BG)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(20, 18))
        ctk.CTkLabel(
            brand,
            text="PhotoVault",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="Vault local confiavel",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=10)
        for index, (view_id, label) in enumerate(NAV_ITEMS, start=1):
            self._create_nav_button(index, view_id, label)

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=16)
        ctk.CTkLabel(
            footer,
            text="v1.0.0",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        shell = ctk.CTkFrame(self.app, corner_radius=0, fg_color=APP_BG)
        shell.pack(side="right", fill="both", expand=True)

        topbar = ctk.CTkFrame(shell, height=64, corner_radius=0, fg_color=APP_BG)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar,
            textvariable=self.step_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(side="left", padx=(24, 12), pady=18)

        ctk.CTkLabel(
            topbar,
            textvariable=self.summary_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="e",
        ).pack(side="right", padx=24, pady=18)

        ctk.CTkFrame(shell, height=1, fg_color=BORDER).pack(fill="x")

        self.content = ctk.CTkFrame(shell, corner_radius=0, fg_color=APP_BG)
        self.content.pack(fill="both", expand=True)

    def _create_nav_button(self, index: int, view_id: str, label: str):
        row = ctk.CTkFrame(self.nav_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)

        btn = ctk.CTkButton(
            row,
            text=f"{index:02d}  {label}",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color="transparent",
            text_color=TEXT_MUTED,
            hover_color=SURFACE_ALT,
            corner_radius=8,
            height=38,
            command=lambda vid=view_id: self.navigate(vid),
        )
        btn.pack(fill="x")

        if view_id == "duplicates":
            badge = ctk.CTkLabel(
                row,
                textvariable=self.dup_badge_var,
                fg_color=ACCENT,
                text_color="#04110f",
                corner_radius=9,
                width=22,
                height=18,
                font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            )
            badge.place(relx=1.0, rely=0.5, anchor="e", x=-8)

        self.nav_buttons[view_id] = btn

    def _load_views(self):
        from gui.views.dashboard import DashboardView
        from gui.views.organize import OrganizeView
        from gui.views.vault import VaultView
        from gui.views.sources import SourcesView
        from gui.views.inventory import InventoryView
        from gui.views.compare import CompareView
        from gui.views.rules import RulesView
        from gui.views.preview import PreviewView
        from gui.views.duplicates import DuplicatesView
        from gui.views.progress import ProgressView
        from gui.views.report import ReportView
        from gui.views.settings import SettingsView

        view_classes = {
            "organize": OrganizeView,
            "vault": VaultView,
            "dashboard": DashboardView,
            "sources": SourcesView,
            "inventory": InventoryView,
            "compare": CompareView,
            "rules": RulesView,
            "preview": PreviewView,
            "duplicates": DuplicatesView,
            "progress": ProgressView,
            "report": ReportView,
            "history": DashboardView,
            "settings": SettingsView,
        }

        for view_id, cls in view_classes.items():
            frame = ctk.CTkFrame(self.content, fg_color=APP_BG, corner_radius=0)
            view = cls(frame, self.app, self)
            self.views[view_id] = (frame, view)

    def navigate(self, view_id: str):
        for frame, _view in self.views.values():
            frame.pack_forget()

        for vid, btn in self.nav_buttons.items():
            if vid == view_id:
                btn.configure(fg_color=SURFACE, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

        frame, view = self.views[view_id]
        frame.pack(fill="both", expand=True)
        self.current_view = view_id
        self._refresh_topbar(view_id)

        if hasattr(view, "refresh"):
            view.refresh()

    def _refresh_topbar(self, view_id: str):
        labels = {vid: label for vid, label in NAV_ITEMS}
        self.step_var.set(labels.get(view_id, "PhotoVault"))

        state = self.app.app_state
        sources = state.get("sources", [])
        destination = state.get("destination")
        plan = state.get("plan")
        source_count = len(sources)
        total = 0
        for src in sources:
            total += src.get("total", 0)

        parts = [f"{source_count} fonte{'s' if source_count != 1 else ''}"]
        if total:
            parts.append(f"{format_count(total)} arquivos")
        if destination:
            parts.append(f"Destino: {destination}")
        if plan:
            parts.append(f"Plano: {format_count(plan.total)} itens")
        self.summary_var.set("  |  ".join(parts) if parts else "Nenhuma sessao configurada")

    def update_dup_badge(self, count: int):
        self.dup_badge_var.set(str(count) if count > 0 else "")
