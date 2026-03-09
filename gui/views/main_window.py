import customtkinter as ctk
from gui.app import (PhotoVaultApp, COLOR_SIDEBAR, COLOR_BG, COLOR_ACCENT,
                     COLOR_TEXT, COLOR_TEXT_DIM, COLOR_BORDER, COLOR_ACCENT2,
                     FONT_FAMILY, FONT_SIZE_BODY, FONT_SIZE_SMALL)

NAV_ITEMS = [
    ('dashboard',   'Dashboard',    '⊞'),
    ('sources',     'Fontes',       '◈'),
    ('rules',       'Regras',       '⚙'),
    ('preview',     'Preview',      '◎'),
    ('duplicates',  'Duplicatas',   '⧉'),
    ('progress',    'Executar',     '▶'),
    ('report',      'Relatório',    '▦'),
]


class MainWindow:
    def __init__(self, app: PhotoVaultApp):
        self.app = app
        self.current_view = None
        self.views: dict = {}
        self.nav_buttons: dict = {}
        self.dup_badge_var = ctk.StringVar(value='')

        self._build_layout()
        self._load_views()
        self.navigate('dashboard')

    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self.app, width=210, corner_radius=0,
            fg_color=COLOR_SIDEBAR
        )
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # Logo area
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color='transparent', height=80)
        logo_frame.pack(fill='x', pady=(20, 10))
        logo_frame.pack_propagate(False)

        ctk.CTkLabel(
            logo_frame, text='📷', font=(FONT_FAMILY, 28)
        ).pack(pady=(10, 0))
        ctk.CTkLabel(
            logo_frame, text='PhotoVault',
            font=(FONT_FAMILY, 14, 'bold'), text_color=COLOR_ACCENT2
        ).pack()

        # Separator
        ctk.CTkFrame(self.sidebar, height=1, fg_color=COLOR_BORDER).pack(fill='x', padx=15, pady=10)

        # Nav buttons
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        self.nav_frame.pack(fill='x', padx=8)

        for view_id, label, icon in NAV_ITEMS:
            self._create_nav_button(view_id, label, icon)

        # Bottom: version label
        ctk.CTkLabel(
            self.sidebar, text='v1.0.0',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='bottom', pady=15)

        # Content area
        self.content = ctk.CTkFrame(
            self.app, corner_radius=0, fg_color=COLOR_BG
        )
        self.content.pack(side='right', fill='both', expand=True)

    def _create_nav_button(self, view_id: str, label: str, icon: str):
        frame = ctk.CTkFrame(self.nav_frame, fg_color='transparent')
        frame.pack(fill='x', pady=2)

        btn = ctk.CTkButton(
            frame,
            text=f"  {icon}  {label}",
            anchor='w',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent',
            text_color=COLOR_TEXT_DIM,
            hover_color=COLOR_ACCENT,
            corner_radius=8,
            height=40,
            command=lambda vid=view_id: self.navigate(vid)
        )
        btn.pack(fill='x')

        # Badge for duplicates
        if view_id == 'duplicates':
            badge = ctk.CTkLabel(
                frame, textvariable=self.dup_badge_var,
                fg_color=COLOR_ACCENT, text_color='white',
                corner_radius=10, width=24, height=20,
                font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold')
            )
            badge.place(relx=1.0, rely=0.5, anchor='e', x=-8)

        self.nav_buttons[view_id] = btn

    def _load_views(self):
        from gui.views.dashboard import DashboardView
        from gui.views.sources import SourcesView
        from gui.views.rules import RulesView
        from gui.views.preview import PreviewView
        from gui.views.duplicates import DuplicatesView
        from gui.views.progress import ProgressView
        from gui.views.report import ReportView

        view_classes = {
            'dashboard': DashboardView,
            'sources': SourcesView,
            'rules': RulesView,
            'preview': PreviewView,
            'duplicates': DuplicatesView,
            'progress': ProgressView,
            'report': ReportView,
        }

        for view_id, cls in view_classes.items():
            frame = ctk.CTkFrame(self.content, fg_color=COLOR_BG, corner_radius=0)
            view = cls(frame, self.app, self)
            self.views[view_id] = (frame, view)

    def navigate(self, view_id: str):
        # Hide all views
        for vid, (frame, view) in self.views.items():
            frame.pack_forget()

        # Update nav button styles
        for vid, btn in self.nav_buttons.items():
            if vid == view_id:
                btn.configure(fg_color=COLOR_ACCENT, text_color='white')
            else:
                btn.configure(fg_color='transparent', text_color=COLOR_TEXT_DIM)

        # Show selected view
        frame, view = self.views[view_id]
        frame.pack(fill='both', expand=True)
        self.current_view = view_id

        # Refresh view if it has a refresh method
        if hasattr(view, 'refresh'):
            view.refresh()

    def update_dup_badge(self, count: int):
        if count > 0:
            self.dup_badge_var.set(str(count))
        else:
            self.dup_badge_var.set('')
