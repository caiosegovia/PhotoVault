import customtkinter as ctk
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DARK_BG = '#1a1a2e'
CARD_BG = '#0f3460'
ACCENT_COLORS = ['#14a085', '#0d7377', '#f39c12', '#e74c3c', '#9b59b6', '#3498db']


def _apply_dark_style(fig, ax):
    fig.patch.set_facecolor(CARD_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors='#888888', labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor('#2a2a4a')


class StorageDonutChart(ctk.CTkFrame):
    def __init__(self, parent, data: dict, **kw):
        super().__init__(parent, fg_color='transparent', **kw)
        self._build(data)

    def _build(self, data: dict):
        labels = list(data.keys())
        values = list(data.values())

        if not any(v > 0 for v in values):
            ctk.CTkLabel(self, text='Sem dados', text_color='#888').pack(expand=True)
            return

        fig, ax = plt.subplots(figsize=(3.5, 2.8), dpi=90)
        _apply_dark_style(fig, ax)

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=ACCENT_COLORS[:len(labels)],
            autopct='%1.0f%%', startangle=90,
            wedgeprops=dict(width=0.55, edgecolor=CARD_BG, linewidth=2),
            textprops={'color': '#e0e0e0', 'fontsize': 9}
        )
        for at in autotexts:
            at.set_color('white')
            at.set_fontsize(8)

        ax.set_aspect('equal')
        fig.tight_layout(pad=0.5)

        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        plt.close(fig)


class StorageBarChart(ctk.CTkFrame):
    def __init__(self, parent, data: dict, **kw):
        super().__init__(parent, fg_color='transparent', **kw)
        self._build(data)

    def _build(self, data: dict):
        if not data:
            ctk.CTkLabel(self, text='Sem dados de ano disponíveis.', text_color='#888').pack(expand=True)
            return

        years = sorted(data.keys())
        counts = [data[y] for y in years]

        fig, ax = plt.subplots(figsize=(5.5, 2.8), dpi=90)
        _apply_dark_style(fig, ax)

        bars = ax.bar(
            [str(y) for y in years], counts,
            color=ACCENT_COLORS[0], edgecolor=CARD_BG, linewidth=0.5
        )
        ax.set_ylabel('Fotos', color='#888888', fontsize=8)
        ax.yaxis.label.set_color('#888888')

        for bar, count in zip(bars, counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                str(count), ha='center', va='bottom',
                color='#e0e0e0', fontsize=7
            )

        fig.tight_layout(pad=0.5)
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        plt.close(fig)
