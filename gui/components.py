import customtkinter as ctk

from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_HEADER,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    RADIUS_MD,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    TEXT_MUTED,
)


def page_frame(parent):
    frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=24, pady=24)
    return frame


def page_header(parent, title: str, subtitle: str = ""):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", pady=(0, 18))

    text_col = ctk.CTkFrame(frame, fg_color="transparent")
    text_col.pack(side="left", fill="x", expand=True)

    ctk.CTkLabel(
        text_col,
        text=title,
        font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
        text_color=TEXT,
        anchor="w",
    ).pack(anchor="w")

    if subtitle:
        ctk.CTkLabel(
            text_col,
            text=subtitle,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

    return frame


def section(parent, title: str = "", subtitle: str = ""):
    card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=RADIUS_MD, border_width=1, border_color=BORDER)
    card.pack(fill="x", pady=(0, 14))

    if title or subtitle:
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 10))
        if title:
            ctk.CTkLabel(
                header,
                text=title,
                font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"),
                text_color=TEXT,
                anchor="w",
            ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                text_color=TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", pady=(3, 0))

    return card


def primary_button(parent, text: str, command=None, width: int = 150, height: int = 38):
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=RADIUS_MD,
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        text_color="#04110f",
        font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
    )


def ghost_button(parent, text: str, command=None, width: int = 140, height: int = 38):
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=RADIUS_MD,
        fg_color="transparent",
        hover_color=SURFACE_ALT,
        border_width=1,
        border_color=BORDER,
        text_color=TEXT,
        font=(FONT_FAMILY, FONT_SIZE_BODY),
    )


def metric_tile(parent, title: str, value: str, subtitle: str = ""):
    tile = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=RADIUS_MD)
    ctk.CTkLabel(
        tile,
        text=title,
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
        text_color=TEXT_MUTED,
        anchor="w",
    ).pack(anchor="w", padx=14, pady=(12, 2))
    value_label = ctk.CTkLabel(
        tile,
        text=value,
        font=(FONT_FAMILY, 20, "bold"),
        text_color=TEXT,
        anchor="w",
    )
    value_label.pack(anchor="w", padx=14)
    ctk.CTkLabel(
        tile,
        text=subtitle,
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
        text_color=TEXT_MUTED,
        anchor="w",
    ).pack(anchor="w", padx=14, pady=(2, 12))
    return tile, value_label


def empty_state(parent, text: str):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    box.pack(fill="x", padx=18, pady=24)
    ctk.CTkLabel(
        box,
        text=text,
        font=(FONT_FAMILY, FONT_SIZE_BODY),
        text_color=TEXT_MUTED,
    ).pack()
    return box
