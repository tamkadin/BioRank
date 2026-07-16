import os
from tkinter import ttk
import customtkinter as ctk
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, PRIMARY, SOFT_BLUE, TEXT_MAIN, TEXT_MUTED,
    STATUS_READY, STATUS_MISSING, STATUS_ERROR,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)

class DataTable(ctk.CTkFrame):
    def __init__(self, master, columns, column_widths=None, **kwargs):
        super().__init__(master, fg_color="#FFFFFF", border_color=BORDER, border_width=1, corner_radius=8, **kwargs)
        self.columns = columns
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        self.vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=(6, 0))
        self.hsb.grid(row=1, column=0, sticky="ew", padx=(6, 0), pady=(0, 6))
        
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except:
            pass
            
        self.style.configure("Custom.Treeview",
                            background="#FFFFFF",
                            foreground=TEXT_MAIN,
                            fieldbackground="#FFFFFF",
                            rowheight=34,
                            gridcolor=BORDER,
                            font=(FONT_FAMILY_BODY, 12))
        self.style.configure("Custom.Treeview.Heading",
                            background=SOFT_BLUE,
                            foreground=TEXT_MAIN,
                            font=(FONT_FAMILY_HEADER, 12, "bold"),
                            borderwidth=1,
                            relief="flat")
        self.style.map("Custom.Treeview.Heading",
                      background=[('active', BORDER)])
        self.style.map("Custom.Treeview",
                      background=[('selected', "#E0E7FF")],
                      foreground=[('selected', PRIMARY)])
        self.tree.configure(style="Custom.Treeview")
        
        for col in columns:
            self.tree.heading(col, text=col, anchor="w")
            if column_widths and col in column_widths:
                self.tree.column(col, width=column_widths[col], anchor="w", minwidth=60)
            else:
                self.tree.column(col, width=120, anchor="w", minwidth=60)
                
        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd", background=APP_BG)
        self.tree.tag_configure("oncokb_hit", background="#E8F5E9", foreground="#2E7D32")
        
    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
    def insert_rows(self, rows_data):
        self.clear()
        for idx, row in enumerate(rows_data):
            is_hit = False
            if len(row) >= 5 and (row[4] is True or row[4] == "Yes"):
                is_hit = True
                
            tag = "oncokb_hit" if is_hit else ("even" if idx % 2 == 0 else "odd")
            self.tree.insert("", "end", values=row, tags=(tag,))


class DatasetCard(ctk.CTkFrame):
    def __init__(self, master, title, key, initial_path="", initial_status="Missing", browse_callback=None, **kwargs):
        super().__init__(master, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8, **kwargs)
        self.key = key
        self.browse_callback = browse_callback
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=14, pady=(14, 6))
        
        self.title_label = ctk.CTkLabel(self.top_frame, text=title, font=(FONT_FAMILY_HEADER, 15), text_color=TEXT_MAIN, anchor="w")
        self.title_label.pack(side="left")
        
        self.status_badge = ctk.CTkLabel(self.top_frame, text="", font=(FONT_FAMILY_HEADER, 12, "bold"), corner_radius=4, padx=8, pady=3)
        self.status_badge.pack(side="right")
        
        self.path_label = ctk.CTkLabel(self, text="", font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MUTED, anchor="w")
        self.path_label.pack(fill="x", padx=14, pady=(0, 10))
        
        self.browse_btn = ctk.CTkButton(self, text="Browse", font=(FONT_FAMILY_HEADER, 13, "bold"),
                                       fg_color=SOFT_BLUE, text_color=PRIMARY, hover_color=BORDER,
                                       height=36, width=95, corner_radius=6, command=self._on_browse)
        self.browse_btn.pack(anchor="e", padx=14, pady=(0, 14))
        
        self.update_state(initial_path, initial_status)
        
    def update_state(self, path, status):
        if not path:
            display_path = "Browse dataset manually..."
        else:
            display_path = os.path.basename(path)
            if len(display_path) > 28:
                display_path = display_path[:25] + "..."
        self.path_label.configure(text=display_path)
        
        if status == "Ready":
            self.status_badge.configure(text="Ready", fg_color="#E8F5E9", text_color=STATUS_READY)
        elif status == "Missing":
            self.status_badge.configure(text="Missing", fg_color="#FFF3E0", text_color=STATUS_MISSING)
        else:
            self.status_badge.configure(text="Invalid", fg_color="#FFEBEE", text_color=STATUS_ERROR)
            
    def _on_browse(self):
        if self.browse_callback:
            self.browse_callback(self.key)


class ProgressOverlay(ctk.CTkFrame):
    def __init__(self, master, cancel_callback=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.backdrop = ctk.CTkFrame(self, fg_color=APP_BG)
        self.backdrop.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        
        self.dialog = ctk.CTkFrame(self.backdrop, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=12, width=460, height=220)
        self.dialog.place(relx=0.5, rely=0.5, anchor="center")
        
        self.status_label = ctk.CTkLabel(self.dialog, text="Initializing analytical workflow...", font=(FONT_FAMILY_HEADER, 17), text_color=TEXT_MAIN)
        self.status_label.pack(pady=(32, 14), padx=24)
        
        self.progress_bar = ctk.CTkProgressBar(self.dialog, progress_color=PRIMARY, fg_color=BORDER, height=8, width=340)
        self.progress_bar.pack(pady=8)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        
        self.cancel_btn = ctk.CTkButton(self.dialog, text="Cancel Execution", font=(FONT_FAMILY_HEADER, 14, "bold"),
                                       fg_color=STATUS_ERROR, hover_color="#B71C1C", text_color="#FFFFFF",
                                       command=cancel_callback, height=44, width=210, corner_radius=6)
        self.cancel_btn.pack(pady=(22, 22))
        
    def update_progress(self, progress, status_text):
        self.status_label.configure(text=status_text)
        if progress >= 0.0:
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(progress)
        else:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
