import os
import sys
import webbrowser
import customtkinter as ctk
from tkinter import Canvas, TclError
from PIL import Image
import threading
import math
import random
from core.scanner import run_db_scan
from core.storage import save_json_history, format_duration_logic

APP_VERSION = "1.5.0"
APP_REPO_URL = "https://github.com/Trukitro/Etch-DB-Mapper"

HELP_TEXT = """\
GUÍA RÁPIDA — Etch-DB-Mapper

1. CONECTAR A UNA BASE DE DATOS
   • Click en "+ Nuevo Escaneo" (barra lateral).
   • Alias: un nombre corto para identificar la conexión (ej: "Home Server").
   • URI: cadena de conexión pydal. Ejemplos:
       - SQL Server:  mssql4://usuario:clave@host:1433/base
       - PostgreSQL:  postgres://usuario:clave@host:5432/base
   • Click "▶ Escanear". La conexión se guarda de inmediato, aunque el
     escaneo falle - no hace falta volver a escribirla si algo sale mal.

2. SI LA CONEXIÓN FALLA
   • El error aparece en la notificación de arriba y queda guardado junto
     a la conexión (se ve marcada con ⚠ en el Historial de DBs).
   • Seleccioná la conexión en "Historial de DBs", click "⚙️ URI" para
     corregirla, y después "Refrescar" para reintentar. No hace falta
     volver a escribir el alias ni la URI desde cero.
   • Si el error menciona un driver faltante (ej: psycopg2, pyodbc),
     instalalo con el comando que te sugiere el mensaje.

3. EXPLORAR UNA BASE YA ESCANEADA
   • Seleccioná el alias en "Historial de DBs" (✓ = conectado con éxito
     al menos una vez).
   • Pestaña "Explorador": arriba, un resumen rápido (tablas, columnas,
     relaciones, huérfanas). Lista de tablas a la izquierda (🔗 = tiene
     relaciones), columnas y relaciones directas a la derecha. El
     buscador filtra por nombre de tabla o de columna, y muestra cuántos
     resultados encontró. "📋 Copiar DDL" copia un CREATE TABLE
     aproximado de la tabla seleccionada.
   • Pestaña "Mapa Relacional": click "Generar Mapa de Relaciones" para
     ver el diagrama. Arrastrá cualquier tabla con el mouse para
     reacomodarla - la posición queda guardada. "🔄 Auto-Organizar" para
     descartar los cambios manuales y recalcular la distribución. Zoom
     con [-]/[+]/slider (arriba a la derecha) o la rueda del mouse, pan
     con click derecho + arrastrar. Pasar el mouse sobre una tabla o una
     conexión resalta solo sus relaciones y atenúa el resto.
   • Pestaña "Tablas Huérfanas": tablas sin relaciones detectadas.
   • El botón 🌙/☀️ (pie de la barra lateral) cambia entre tema oscuro y
     claro. El Mapa Relacional se mantiene siempre oscuro (es un canvas,
     no se ve bien en claro).

4. MÁS INFORMACIÓN
   • Repo: github.com/Trukitro/Etch-DB-Mapper
   • docs/BACKLOG.md y docs/BUGS.md en el repo para ver qué falta y
     qué se sabe que no funciona todavía.
"""


# ========== NOTIFICACIONES INTEGRADAS EN LA UI ==========

class NotificationBanner(ctk.CTkFrame):
    """Banner de notificación que aparece temporalmente en la interfaz"""
    def __init__(self, parent, message, notification_type="info"):
        super().__init__(parent, height=60, corner_radius=8)
        self.pack(fill="x", padx=15, pady=10)
        
        # Colores según tipo
        colors = {
            "success": ("#28a745", "#f0f8f0"),
            "error": ("#dc3545", "#f8f9fa"),
            "info": ("#0d6efd", "#e7f1ff"),
            "warning": ("#ffc107", "#fff3cd")
        }
        
        bg_color, text_bg = colors.get(notification_type, colors["info"])
        self.configure(fg_color=bg_color)
        
        # Icono + Mensaje
        content_frame = ctk.CTkFrame(self, fg_color=bg_color)
        content_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        icons = {
            "success": "✓",
            "error": "⚠️",
            "info": "ℹ️",
            "warning": "⚡"
        }
        icon = icons.get(notification_type, "•")
        
        msg_label = ctk.CTkLabel(
            content_frame,
            text=f"{icon}  {message}",
            font=("Arial", 11),
            text_color="white"
        )
        msg_label.pack(anchor="w", fill="x", expand=True)
        
        # Botón cerrar
        close_btn = ctk.CTkButton(
            content_frame,
            text="✕",
            width=30,
            height=30,
            font=("Arial", 10),
            fg_color="transparent",
            text_color="white",
            hover_color=bg_color,
            command=self.destroy
        )
        close_btn.pack(side="right", padx=5)
        
        # Auto-desaparecer en 5 segundos (excepto errores)
        if notification_type != "error":
            self.after(5000, self.safe_destroy)
    
    def safe_destroy(self):
        try:
            self.destroy()
        except TclError:
            pass  # el widget ya fue destruido (ej: se cerró la ventana antes)


class DBMapperUI(ctk.CTk):
    def __init__(self, history, storage_path, icon_path, logo_path=None):
        # Tema explícito (en vez de "System") para que el look sea siempre
        # el mismo sin importar la config de Windows del usuario. El botón
        # 🌙/☀️ del footer permite cambiarlo en caliente.
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.history = history
        self.storage_path = storage_path
        self.logo_path = logo_path
        self.zoom_level = 1.0
        self.current_db_name = None
        self.current_table = None
        self.table_cards = {}
        self.scan_in_progress = False
        # Generación de escaneo por alias: si se edita la URI y se reintenta
        # mientras un escaneo viejo del mismo alias sigue en vuelo, el
        # resultado viejo (cuando por fin llegue) se descarta en vez de
        # pisar al nuevo.
        self.scan_generation = {}
        self._scan_counter = 0

        # Estado del Mapa Relacional: posiciones/puertos actuales de cada
        # nodo dibujado, conexiones dibujadas, e índice nodo -> conexiones
        # que lo tocan (para actualizar líneas en vivo al arrastrar y para
        # el resaltado por hover). Se reconstruyen en cada render_map().
        self.map_nodes = {}
        self.map_connections = []
        self.map_node_connections = {}
        self._drag_state = None

        self.title("Etch-DB-Mapper")
        self.geometry("1500x950")
        
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except TclError as e:
                print(f"Aviso: no se pudo aplicar el ícono '{icon_path}' ({e}).", file=sys.stderr)

        self.setup_layout()

        # Cargar historial inicial si existe
        if self.history:
            self.update_history_list()

    def setup_layout(self):
        """Configura el layout completo de la aplicación"""
        # Grid principal: 2 columnas, 2 filas
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)  # La fila 1 es la principal (expandible)

        # ========== FILA 0: NOTIFICACIONES ==========
        self.notifications_frame = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self.notifications_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        # ========== COLUMNA 0: SIDEBAR ==========
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        
        if self.logo_path and os.path.exists(self.logo_path):
            logo_img = Image.open(self.logo_path)
            logo_ratio = logo_img.height / logo_img.width
            logo_w = 260
            logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(logo_w, round(logo_w * logo_ratio)))
            ctk.CTkLabel(self.sidebar, image=logo_ctk, text="").pack(pady=20)
        else:
            ctk.CTkLabel(self.sidebar, text="DB MANAGER PRO", font=("Arial", 22, "bold")).pack(pady=20)
        
        # Panel Nuevo Escaneo (expandible)
        self.setup_scan_panel()

        # Footer: Ayuda / Acerca de (anclado abajo, se packea antes que el
        # historial para que le reserve espacio)
        footer_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(footer_frame, text="❓ Ayuda", fg_color="#5a6268", command=self.show_help).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(footer_frame, text="ℹ️ Acerca de", fg_color="#5a6268", command=self.show_about).pack(side="left", expand=True, fill="x", padx=5)
        self.theme_btn = ctk.CTkButton(footer_frame, text="🌙", width=44, font=("Arial", 14), fg_color="#5a6268", command=self.toggle_theme)
        self.theme_btn.pack(side="left", padx=(5, 0))

        self.history_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="Historial de DBs")
        self.history_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== COLUMNA 1: TABS PRINCIPALES ==========
        self.tabs = ctk.CTkTabview(self, corner_radius=10)
        self.tabs.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tab_explorer = self.tabs.add("🔍 Explorador")
        self.tab_mapper = self.tabs.add("🌐 Mapa Relacional")
        self.tab_orphans = self.tabs.add("📁 Tablas Huérfanas")

        self.setup_explorer_tab()
        self.setup_mapper_tab()
        self.setup_orphans_tab()

    def setup_scan_panel(self):
        """Panel de Nuevo Escaneo expandible en el sidebar"""
        # Frame colapsable
        self.scan_panel_collapsed = True
        
        header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_frame.pack(fill="x", pady=10, padx=20)
        
        btn_toggle = ctk.CTkButton(
            header_frame,
            text="+ Nuevo Escaneo",
            command=self.toggle_scan_panel,
            fg_color="#6f42c1",
            font=("Arial", 11, "bold")
        )
        btn_toggle.pack(fill="x")
        self.btn_new_scan = btn_toggle
        
        # Panel de contenido (inicialmente oculto)
        self.scan_panel_content = ctk.CTkFrame(self.sidebar, fg_color=("gray85", "#2b2b2b"), corner_radius=8)
        self.scan_panel_content.pack(fill="x", padx=10, pady=5)
        self.scan_panel_content.pack_forget()  # Ocultar inicialmente
        
        # Campos
        ctk.CTkLabel(self.scan_panel_content, text="Alias:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        self.entry_alias = ctk.CTkEntry(self.scan_panel_content, placeholder_text="ej: AusBilling")
        self.entry_alias.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.scan_panel_content, text="URI:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        self.entry_uri = ctk.CTkEntry(self.scan_panel_content, placeholder_text="mssql4://user:pass@host:1433/db")
        self.entry_uri.pack(fill="x", padx=10, pady=5)
        
        # Botones
        btn_frame = ctk.CTkFrame(self.scan_panel_content, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        btn_start = ctk.CTkButton(
            btn_frame,
            text="▶ Escanear",
            fg_color="#28a745",
            command=self.start_new_scan,
            state="normal"
        )
        btn_start.pack(side="left", padx=5, expand=True, fill="x")
        self.btn_scan_start = btn_start
        
        btn_clear = ctk.CTkButton(
            btn_frame,
            text="✕ Limpiar",
            fg_color="#dc3545",
            command=lambda: (self.entry_alias.delete(0, "end"), self.entry_uri.delete(0, "end"))
        )
        btn_clear.pack(side="right", padx=5, expand=True, fill="x")

    def setup_explorer_tab(self):
        # Barra Superior del Explorador
        self.exp_top = ctk.CTkFrame(self.tab_explorer, fg_color="transparent")
        self.exp_top.pack(fill="x", pady=5, padx=10)

        self.header_label = ctk.CTkLabel(self.exp_top, text="Seleccione una Base de Datos", font=("Arial", 16, "bold"))
        self.header_label.pack(side="left", padx=10)

        self.btn_refresh = ctk.CTkButton(self.exp_top, text="Refrescar", width=80, fg_color="#28a745", command=self.refresh_current, state="disabled")
        self.btn_refresh.pack(side="right", padx=5)

        self.btn_uri = ctk.CTkButton(self.exp_top, text="⚙️ URI", width=60, fg_color="#5a6268", command=self.edit_uri, state="disabled")
        self.btn_uri.pack(side="right", padx=5)

        # Panel de edición de URI (inicialmente oculto)
        self.uri_editor_frame = ctk.CTkFrame(self.tab_explorer, fg_color=("gray85", "#2b2b2b"), corner_radius=8)
        self.uri_edit_entry = ctk.CTkEntry(self.uri_editor_frame, placeholder_text="mssql4://user:pass@host:1433/db")
        self.uri_edit_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        ctk.CTkButton(self.uri_editor_frame, text="Guardar", width=80, fg_color="#28a745", command=self.save_edited_uri).pack(side="left", padx=5, pady=10)
        ctk.CTkButton(self.uri_editor_frame, text="Cancelar", width=80, fg_color="#dc3545", command=self.hide_uri_editor).pack(side="left", padx=(5, 10), pady=10)
        self.uri_editor_frame.pack_forget()

        # Dashboard de estadísticas (tablas / columnas / relaciones / huérfanas)
        self.stats_frame = ctk.CTkFrame(self.tab_explorer, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(5, 0))

        # Buscador + contador de resultados
        search_row = ctk.CTkFrame(self.tab_explorer, fg_color="transparent")
        search_row.pack(fill="x", padx=20, pady=5)
        self.search_entry = ctk.CTkEntry(search_row, placeholder_text="🔍 Filtrar por nombre de tabla o de columna...")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_tables())
        self.search_results_label = ctk.CTkLabel(search_row, text="", width=110, text_color=("gray40", "gray60"))
        self.search_results_label.pack(side="left", padx=(10, 0))

        # Cuerpo del Explorador (Lista y Detalle)
        self.exp_body = ctk.CTkFrame(self.tab_explorer, fg_color="transparent")
        self.exp_body.pack(fill="both", expand=True, padx=10, pady=5)

        self.table_scroll = ctk.CTkScrollableFrame(self.exp_body, width=300, label_text="Tablas")
        self.table_scroll.pack(side="left", fill="y", padx=(0, 5))

        self.details_frame = ctk.CTkFrame(self.exp_body)
        self.details_frame.pack(side="right", fill="both", expand=True)

        # Encabezado del detalle: nombre de tabla + copiar DDL
        detail_header = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        detail_header.pack(fill="x", padx=10, pady=(10, 0))
        self.table_detail_label = ctk.CTkLabel(detail_header, text="Seleccioná una tabla", font=("Arial", 14, "bold"), anchor="w")
        self.table_detail_label.pack(side="left", fill="x", expand=True)
        self.btn_copy_ddl = ctk.CTkButton(detail_header, text="📋 Copiar DDL", width=110, fg_color="#5a6268", command=self.copy_table_ddl, state="disabled")
        self.btn_copy_ddl.pack(side="right")

        # Columnas (encabezado fijo + lista con badges 🔑/🔗)
        columns_header = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        columns_header.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(columns_header, text="", width=28).pack(side="left")
        ctk.CTkLabel(columns_header, text="CAMPO", font=("Arial", 10, "bold"), text_color=("gray40", "gray60"), anchor="w").pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(columns_header, text="TIPO", font=("Arial", 10, "bold"), text_color=("gray40", "gray60"), anchor="w", width=140).pack(side="left", padx=4)
        ctk.CTkLabel(columns_header, text="NULL", font=("Arial", 10, "bold"), text_color=("gray40", "gray60"), width=70).pack(side="right", padx=6)

        self.columns_frame = ctk.CTkScrollableFrame(self.details_frame, fg_color="transparent")
        self.columns_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        # Área de Relaciones
        self.rel_frame = ctk.CTkScrollableFrame(self.details_frame, height=200, label_text="RELACIONES DIRECTAS")
        self.rel_frame.pack(fill="x", padx=10, pady=5)

    def setup_mapper_tab(self):
        self.map_ctrl = ctk.CTkFrame(self.tab_mapper, height=40, fg_color="transparent")
        self.map_ctrl.pack(fill="x", pady=5)

        ctk.CTkButton(self.map_ctrl, text="Generar Mapa de Relaciones", command=self.render_map, fg_color="#6f42c1").pack(side="left", padx=10)
        ctk.CTkButton(self.map_ctrl, text="🔄 Auto-Organizar", command=self.auto_organize_map, fg_color="#5a6268").pack(side="left", padx=(0, 10))

        # Controles de zoom (movidos acá desde la barra lateral, para
        # dejarle más espacio vertical al Historial de DBs)
        zoom_frame = ctk.CTkFrame(self.map_ctrl, fg_color="transparent")
        zoom_frame.pack(side="right", padx=10)
        ctk.CTkButton(zoom_frame, text="-", width=28, command=lambda: self.adjust_zoom(-0.1)).pack(side="left", padx=2)
        self.zoom_pct_label = ctk.CTkLabel(zoom_frame, text="100%", width=45)
        self.zoom_pct_label.pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="+", width=28, command=lambda: self.adjust_zoom(0.1)).pack(side="left", padx=2)
        self.zoom_slider = ctk.CTkSlider(zoom_frame, from_=0.1, to=2.5, command=self.update_zoom, width=140)
        self.zoom_slider.set(1.0)
        self.zoom_slider.pack(side="left", padx=(8, 2))

        self.canvas = Canvas(self.tab_mapper, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=5)

        # Pan y Zoom
        self.canvas.bind("<ButtonPress-3>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B3-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

    def setup_orphans_tab(self):
        self.orphans_list = ctk.CTkScrollableFrame(self.tab_orphans, label_text="Tablas sin Relaciones Detectadas")
        self.orphans_list.pack(fill="both", expand=True, padx=20, pady=20)

    # --- LÓGICA DE ACTUALIZACIÓN ---
    def get_db_status(self, name):
        """Estado de una conexión guardada: 'success', 'error' o 'pending'.
        Compatible con entradas viejas del historial que no tenían campo
        'status' (siempre eran de un escaneo exitoso, porque antes solo se
        guardaban si el escaneo funcionaba)."""
        entry = self.history.get(name, {})
        return entry.get("status") or ("success" if entry.get("data") else "pending")

    def update_history_list(self):
        for w in self.history_frame.winfo_children(): w.destroy()
        status_icon = {"success": "✓", "error": "⚠", "pending": "…"}
        for name in sorted(self.history.keys()):
            status = self.get_db_status(name)
            icon = status_icon.get(status, "")
            kwargs = dict(
                text=f"{icon}  {name}" if icon else name,
                anchor="w",
                fg_color="transparent",
                command=lambda n=name: self.load_db(n),
            )
            if status == "error":
                kwargs["text_color"] = "#ff6b6b"
            btn = ctk.CTkButton(self.history_frame, **kwargs)
            btn.pack(fill="x", pady=2)

    def load_db(self, name):
        self.current_db_name = name
        self.current_table = None
        db_obj = self.history[name]
        status = self.get_db_status(name)
        last_scan = db_obj.get("last_scan", "Nunca")
        dur = format_duration_logic(db_obj.get("duration_sec", 0))

        if status == "error":
            err = db_obj.get("last_error", "error desconocido")
            self.header_label.configure(text=f"DB: {name} | ⚠ Última conexión falló")
            self.show_notification(
                f"'{name}' no pudo conectar: {err}. Corregí la URI (⚙️ URI) y probá Refrescar.",
                "error",
            )
        elif status == "pending":
            self.header_label.configure(text=f"DB: {name} | Todavía sin conectar con éxito")
        else:
            self.header_label.configure(text=f"DB: {name} | {last_scan} | {dur}")

        self.btn_refresh.configure(state="normal")
        self.btn_uri.configure(state="normal")
        self._update_stats_dashboard()
        self.filter_tables()

    def _update_stats_dashboard(self):
        """Tarjetas de resumen (tablas/columnas/relaciones/huérfanas) arriba
        del Explorador, para tener una vista rápida sin explorar tabla por
        tabla."""
        for w in self.stats_frame.winfo_children(): w.destroy()

        data = self.history.get(self.current_db_name, {}).get("data", {}) if self.current_db_name else {}
        total_tables = len(data)
        total_columns = sum(len(info.get("columns", [])) for info in data.values())
        total_relations = sum(len(info.get("relations", [])) for info in data.values())

        related = set()
        for t, info in data.items():
            if info.get("relations"):
                related.add(t)
            for other_t, other_info in data.items():
                if any(r["ref_table"] == t for r in other_info.get("relations", [])):
                    related.add(t)
        orphans = total_tables - len(related)

        stats = [
            ("🗂", "Tablas", total_tables),
            ("📊", "Columnas", total_columns),
            ("🔗", "Relaciones", total_relations),
            ("📁", "Huérfanas", orphans),
        ]
        for icon, label, value in stats:
            card = ctk.CTkFrame(self.stats_frame, corner_radius=8, fg_color=("gray85", "gray20"))
            card.pack(side="left", padx=(0, 8), fill="x", expand=True)
            ctk.CTkLabel(card, text=f"{icon} {value}", font=("Arial", 16, "bold")).pack(pady=(8, 0), padx=10)
            ctk.CTkLabel(card, text=label, font=("Arial", 10), text_color=("gray40", "gray60")).pack(pady=(0, 8), padx=10)

    def filter_tables(self):
        term = self.search_entry.get().lower().strip()
        for w in self.table_scroll.winfo_children(): w.destroy()
        self.table_cards = {}
        if not self.current_db_name:
            self.search_results_label.configure(text="")
            return

        data = self.history[self.current_db_name].get("data", {})
        matches = []
        for t in sorted(data.keys()):
            if not term:
                matches.append((t, None))
                continue
            if term in t.lower():
                matches.append((t, None))
                continue
            col_hit = next((c["name"] for c in data[t].get("columns", []) if term in c["name"].lower()), None)
            if col_hit:
                matches.append((t, col_hit))

        self.search_results_label.configure(
            text=f"{len(matches)} de {len(data)} tablas" if data else ""
        )
        for t, matched_col in matches:
            self._create_table_card(t, matched_col)

    def _create_table_card(self, t, matched_col=None):
        """Tarjeta clickeable para una tabla en la lista del Explorador:
        ícono, nombre, cantidad de columnas y por qué matcheó la búsqueda
        (si fue por una columna en particular, no por el nombre)."""
        data = self.history[self.current_db_name]["data"]
        info = data[t]
        col_count = len(info.get("columns", []))
        has_relations = len(info.get("relations", [])) > 0
        is_referenced = any(
            any(r["ref_table"] == t for r in other.get("relations", []))
            for other in data.values()
        )
        linked = has_relations or is_referenced
        icon = "🔗" if linked else "▦"

        card = ctk.CTkFrame(self.table_scroll, corner_radius=6, fg_color=("gray85", "gray20"))
        card.pack(fill="x", pady=3, padx=2)

        top = ctk.CTkLabel(card, text=f"{icon} {t}", anchor="w", font=("Arial", 12, "bold"))
        top.pack(fill="x", padx=10, pady=(6, 0))

        subtitle = f"{col_count} columna{'s' if col_count != 1 else ''}"
        if matched_col:
            subtitle += f"  ·  coincide en: {matched_col}"
        sub = ctk.CTkLabel(card, text=subtitle, anchor="w", font=("Arial", 10), text_color=("gray40", "gray60"))
        sub.pack(fill="x", padx=10, pady=(0, 6))

        for widget in (card, top, sub):
            widget.bind("<Button-1>", lambda e, n=t: self.show_table_details(n))
            widget.bind("<Enter>", lambda e, c=card: c.configure(fg_color=("gray80", "gray25")))
            widget.bind("<Leave>", lambda e, c=card, tb=t: c.configure(fg_color=self._card_fg_color(tb)))

        self.table_cards[t] = card
        self._update_table_card_selection()

    def _card_fg_color(self, table_name):
        return ("#cfe6ff", "#1f3a52") if table_name == self.current_table else ("gray85", "gray20")

    def _update_table_card_selection(self):
        """Resalta la tarjeta de la tabla actualmente seleccionada sin
        reconstruir toda la lista."""
        for t, card in self.table_cards.items():
            card.configure(fg_color=self._card_fg_color(t))

    def show_table_details(self, t_name):
        self.current_table = t_name
        self._update_table_card_selection()
        info = self.history[self.current_db_name]["data"][t_name]
        fk_columns = {r["col"] for r in info.get("relations", [])}

        self.table_detail_label.configure(text=f"▦ {t_name}")
        self.btn_copy_ddl.configure(state="normal")

        # Limpiar y llenar columnas (con badges 🔑 PK / 🔗 FK)
        for w in self.columns_frame.winfo_children(): w.destroy()
        for idx, c in enumerate(info.get("columns", [])):
            is_pk = bool(c.get("is_pk"))
            is_fk = c["name"] in fk_columns
            if is_pk:
                row_bg = ("#fff3cd", "#3a3020")
                badge = "🔑"
            elif is_fk:
                row_bg = ("#dbeeff", "#1c3a52")
                badge = "🔗"
            else:
                row_bg = ("gray92", "gray17") if idx % 2 == 0 else ("gray88", "gray20")
                badge = ""

            row = ctk.CTkFrame(self.columns_frame, fg_color=row_bg, corner_radius=4)
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=badge, width=28, font=("Arial", 11)).pack(side="left")
            ctk.CTkLabel(row, text=c["name"], anchor="w", font=("Consolas", 12, "bold")).pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(row, text=c.get("type", ""), anchor="w", font=("Consolas", 11), text_color=("gray30", "gray70"), width=140).pack(side="left", padx=4)
            null_txt = "NULL" if c.get("null") == "YES" else "NOT NULL"
            ctk.CTkLabel(row, text=null_txt, width=70, font=("Arial", 10),
                        text_color=("#b02a37", "#ff8080") if null_txt == "NOT NULL" else ("gray50", "gray50")).pack(side="right", padx=6)

        # Limpiar y Llenar Relaciones
        for w in self.rel_frame.winfo_children(): w.destroy()
        for r in info.get("relations", []):
            f = ctk.CTkFrame(self.rel_frame)
            f.pack(fill="x", pady=2, padx=5)
            ctk.CTkLabel(f, text=f"🔗 {r['col']} -> {r['ref_table']}", font=("Consolas", 11)).pack(side="left", padx=10)
            ctk.CTkButton(f, text="INVESTIGAR", width=80, height=24,
                         command=lambda x=r['ref_table']: self.show_table_details(x)).pack(side="right", padx=5)

    def copy_table_ddl(self):
        """Copia al portapapeles un CREATE TABLE aproximado de la tabla
        seleccionada, a partir de los tipos que devolvió INFORMATION_SCHEMA
        (no es DDL 100% ejecutable en todos los motores, es una referencia
        rápida)."""
        if not self.current_db_name or not self.current_table:
            return
        info = self.history[self.current_db_name]["data"][self.current_table]
        col_lines = []
        for c in info.get("columns", []):
            line = f"    {c['name']} {c.get('type', '')}"
            if c.get("null") == "NO":
                line += " NOT NULL"
            if c.get("is_pk"):
                line += " PRIMARY KEY"
            col_lines.append(line)
        ddl = f"CREATE TABLE {self.current_table} (\n" + ",\n".join(col_lines) + "\n);"

        self.clipboard_clear()
        self.clipboard_append(ddl)
        self.show_notification(f"DDL de '{self.current_table}' copiado al portapapeles", "success")

    def toggle_scan_panel(self):
        """Muestra/oculta el panel de nuevo escaneo"""
        if self.scan_panel_collapsed:
            self.scan_panel_content.pack(fill="x", padx=10, pady=5)
            self.btn_new_scan.configure(text="- Nuevo Escaneo")
            self.scan_panel_collapsed = False
        else:
            self.scan_panel_content.pack_forget()
            self.btn_new_scan.configure(text="+ Nuevo Escaneo")
            self.scan_panel_collapsed = True

    def start_new_scan(self):
        """Inicia un nuevo escaneo desde el panel integrado"""
        alias = self.entry_alias.get().strip()
        uri = self.entry_uri.get().strip()

        # Validación
        if not alias:
            self.show_notification("El alias no puede estar vacío", "error")
            return
        if not uri:
            self.show_notification("La URI de conexión no puede estar vacía", "error")
            return

        # Guardar la conexión YA, antes de intentar el escaneo. Así, si falla
        # o el driver no está instalado, la URI no se pierde y no hay que
        # volver a escribirla - se puede corregir y reintentar desde el
        # historial.
        self.save_history_entry(alias, uri, status="pending")
        self.update_history_list()

        # Deshabilitar botones mientras escanea
        self.btn_scan_start.configure(state="disabled")
        self.btn_new_scan.configure(state="disabled")
        self.scan_in_progress = True

        # Mostrar notificación de inicio
        self.show_notification(f"Iniciando escaneo de {alias}...", "info")

        # Ejecutar escaneo en hilo separado
        self.start_scan_thread(uri, alias)

    def save_history_entry(self, alias, uri, status, data=None, last_scan=None, duration_sec=None, last_error=None):
        """Crea/actualiza una entrada del historial y la persiste en disco.
        Preserva el último escaneo exitoso (data/last_scan/duration_sec) si
        no se pasa uno nuevo, para no perder tablas ya exploradas cuando un
        reintento falla."""
        existing = self.history.get(alias, {})
        self.history[alias] = {
            "uri": uri,
            "status": status,
            "data": data if data is not None else existing.get("data", {}),
            "last_scan": last_scan if last_scan is not None else existing.get("last_scan", "Nunca"),
            "duration_sec": duration_sec if duration_sec is not None else existing.get("duration_sec", 0),
            "last_error": last_error,
        }
        save_json_history(self.storage_path, self.history)

    def start_scan_thread(self, uri, alias):
        """Ejecuta el escaneo en hilo separado"""
        self._scan_counter += 1
        my_generation = self._scan_counter
        self.scan_generation[alias] = my_generation

        def is_stale():
            # Si se editó la URI y se reintentó mientras este hilo seguía
            # corriendo, ya hay un escaneo más nuevo para este alias: el
            # resultado de éste llegó tarde, no corresponde escribirlo.
            return self.scan_generation.get(alias) != my_generation

        def task():
            try:
                res = run_db_scan(uri)
                if is_stale():
                    return
                if res["status"] == "success":
                    self.save_history_entry(
                        alias, uri, status="success",
                        data=res["data"], last_scan=res["last_scan"], duration_sec=res["duration_sec"],
                    )
                    duration = format_duration_logic(res["duration_sec"])
                    num_tables = len(res["data"])

                    # Actualizar UI en hilo principal
                    self.after(0, lambda: self.update_history_list())
                    self.after(0, lambda: self.load_db(alias))
                    self.after(0, lambda: self.show_notification(
                        f"✓ Escaneo exitoso: {num_tables} tablas en {duration}",
                        "success"
                    ))
                    self.after(0, self.clear_scan_form)
                else:
                    msg = res.get("message", "Error desconocido")
                    self.save_history_entry(alias, uri, status="error", last_error=msg)
                    self.after(0, lambda: self.update_history_list())
                    self.after(0, lambda: self.show_notification(
                        f"Error: {msg}",
                        "error"
                    ))
            except Exception as e:
                if not is_stale():
                    self.save_history_entry(alias, uri, status="error", last_error=str(e))
                    self.after(0, lambda: self.update_history_list())
                    self.after(0, lambda: self.show_notification(
                        f"Excepción: {str(e)}",
                        "error"
                    ))
            finally:
                # Re-habilitar botones (siempre, sin importar si este hilo
                # era el más reciente - si no se re-habilitan quedan
                # trabados)
                self.after(0, lambda: self.btn_scan_start.configure(state="normal"))
                self.after(0, lambda: self.btn_new_scan.configure(state="normal"))
                self.after(0, lambda: setattr(self, 'scan_in_progress', False))

        threading.Thread(target=task, daemon=True).start()

    def clear_scan_form(self):
        """Limpia el formulario de escaneo"""
        self.entry_alias.delete(0, "end")
        self.entry_uri.delete(0, "end")

    def show_notification(self, message, notification_type="info"):
        """Muestra una notificación en el panel de notificaciones superior"""
        banner = NotificationBanner(self.notifications_frame, message, notification_type)

    def render_map(self):
        """
        Renderiza el mapa relacional con:
        - Zonificación Urbana: Tablas con relaciones en el mapa, huérfanas en lista
        - Posicionamiento: usa la posición guardada de cada tabla si existe
          (arrastrada a mano o de un render anterior); si no, distribución
          radial + detección de solapamientos, solo entre las tablas sin
          posición guardada.
        - Dibujo Completo: Usa draw_node para renderizar cada tabla con campos y puertos
        """
        if not self.current_db_name: return
        self.canvas.delete("all")
        db_entry = self.history[self.current_db_name]
        db_data = db_entry.get("data", {})
        saved_positions = db_entry.get("positions", {})

        # Reset del estado de interacción del mapa (se reconstruye acá)
        self.map_nodes = {}
        self.map_connections = []
        self.map_node_connections = {}
        self._drag_state = None

        # ========== FASE 1: FILTRADO (Zonificación) ==========
        # Identificar tablas con relaciones (origen o destino)
        related = set()
        for table_name, table_info in db_data.items():
            # Si la tabla tiene FKs salientes
            if len(table_info.get("relations", [])) > 0:
                related.add(table_name)
            # Si otra tabla apunta a ésta (FK entrante)
            for other_table, other_info in db_data.items():
                if any(r['ref_table'] == table_name for r in other_info.get("relations", [])):
                    related.add(table_name)

        related = sorted(list(related))
        orphans = [t for t in db_data if t not in related]

        # ========== FASE 2: LLENAR PESTAÑA DE HUÉRFANAS ==========
        for w in self.orphans_list.winfo_children(): w.destroy()
        if orphans:
            ctk.CTkLabel(self.orphans_list, text=f"Total: {len(orphans)} tablas sin relaciones",
                        font=("Arial", 12, "bold")).pack(fill="x", padx=20, pady=10)
        for t in orphans:
            ctk.CTkLabel(self.orphans_list, text=f"• {t}", anchor="w").pack(fill="x", padx=30)

        if not related:
            ctk.CTkLabel(self.canvas, text="No hay tablas con relaciones",
                        font=("Arial", 14)).pack(expand=True)
            return

        # ========== FASE 3: POSICIONAMIENTO ==========
        # Las tablas con posición guardada quedan "fijas" (no se mueven en
        # la resolución de solapamientos); el resto arranca en distribución
        # radial y se acomoda alrededor de las fijas.
        node_bboxes = {}
        center_x, center_y = 500, 500
        base_radius = 400
        zoom = self.zoom_level

        for i, table in enumerate(related):
            columns = db_data[table].get("columns", [])
            estimated_width = max(int(180 * zoom), int(20 + len(table) * 7 * zoom))
            estimated_height = int(28 * zoom) + (len(columns) * int(18 * zoom)) + int(16 * zoom)

            saved = saved_positions.get(table)
            if saved:
                x, y = saved["x"], saved["y"]
                fixed = True
            else:
                angle = (2 * math.pi * i) / len(related) if len(related) > 1 else 0
                x = center_x + base_radius * math.cos(angle)
                y = center_y + base_radius * math.sin(angle)
                fixed = False

            node_bboxes[table] = {"x": x, "y": y, "width": estimated_width, "height": estimated_height, "fixed": fixed}

        # ========== DETECCIÓN Y RESOLUCIÓN DE SOLAPAMIENTOS ==========
        # Se salta por completo si todas las posiciones ya están fijas (nada
        # para acomodar) - evita trabajo innecesario en mapas grandes.
        if any(not b["fixed"] for b in node_bboxes.values()):
            max_iterations = 50
            iteration = 0
            min_distance = 50

            while iteration < max_iterations:
                overlaps_found = False

                for i, table1 in enumerate(related):
                    for j, table2 in enumerate(related):
                        if i >= j:
                            continue

                        bbox1 = node_bboxes[table1]
                        bbox2 = node_bboxes[table2]
                        if bbox1["fixed"] and bbox2["fixed"]:
                            continue  # ninguno se puede mover

                        left1, right1 = bbox1["x"], bbox1["x"] + bbox1["width"]
                        top1, bottom1 = bbox1["y"], bbox1["y"] + bbox1["height"]
                        left2, right2 = bbox2["x"], bbox2["x"] + bbox2["width"]
                        top2, bottom2 = bbox2["y"], bbox2["y"] + bbox2["height"]

                        if not (right1 < left2 or right2 < left1 or bottom1 < top2 or bottom2 < top1):
                            overlaps_found = True

                            center1 = (bbox1["x"] + bbox1["width"]/2, bbox1["y"] + bbox1["height"]/2)
                            center2 = (bbox2["x"] + bbox2["width"]/2, bbox2["y"] + bbox2["height"]/2)
                            dx = center1[0] - center2[0]
                            dy = center1[1] - center2[1]
                            dist = math.sqrt(dx*dx + dy*dy) + 0.001

                            push_x = (dx / dist) * min_distance
                            push_y = (dy / dist) * min_distance

                            # Si uno de los dos está fijo, todo el empuje
                            # recae sobre el que se puede mover.
                            if not bbox1["fixed"]:
                                factor = 0.5 if not bbox2["fixed"] else 1.0
                                bbox1["x"] += push_x * factor
                                bbox1["y"] += push_y * factor
                            if not bbox2["fixed"]:
                                factor = 0.5 if not bbox1["fixed"] else 1.0
                                bbox2["x"] -= push_x * factor
                                bbox2["y"] -= push_y * factor

                if not overlaps_found:
                    break
                iteration += 1

        # ========== FASE 4: DIBUJO DE NODOS CON draw_node ==========
        for table in related:
            bbox = node_bboxes[table]
            columns = db_data[table].get("columns", [])
            fk_columns = {r["col"] for r in db_data[table].get("relations", [])}

            node_data = self.draw_node(
                self.canvas,
                bbox["x"],
                bbox["y"],
                table,
                columns,
                fk_columns,
                node_id=table
            )

            self.map_nodes[table] = node_data
            self.map_node_connections[table] = []

        # Cachear las posiciones (incluidas las recién auto-calculadas) para
        # que el mapa sea estable entre renders, no solo lo que se arrastró
        # a mano.
        db_entry["positions"] = {t: {"x": node_bboxes[t]["x"], "y": node_bboxes[t]["y"]} for t in related}
        save_json_history(self.storage_path, self.history)

        # ========== FASE 5: DIBUJO DE CONEXIONES ==========
        colors_fk = ["#33FFF3", "#FFD700", "#FF69B4", "#00FF00", "#FF8C00", "#1E90FF"]
        fk_index = 0

        for table, table_info in db_data.items():
            if table not in self.map_nodes:
                continue

            for rel in table_info.get("relations", []):
                ref_table = rel['ref_table']
                col_name = rel['col']

                if ref_table not in self.map_nodes:
                    continue

                source_node = self.map_nodes[table]
                target_node = self.map_nodes[ref_table]

                if col_name in source_node["ports"] and len(target_node["ports"]) > 0:
                    color = colors_fk[fk_index % len(colors_fk)]
                    fk_index += 1
                    conn = self._draw_connection(table, ref_table, col_name, color)
                    self.map_connections.append(conn)
                    self.map_node_connections.setdefault(table, []).append(conn)
                    self.map_node_connections.setdefault(ref_table, []).append(conn)

    def _connection_points(self, source_table, col_name, target_table):
        """Calcula los 4 puntos (con curvatura) de la línea de conexión
        entre dos nodos, usando su posición ACTUAL (self.map_nodes), para
        poder recalcularla en vivo mientras se arrastra un nodo."""
        source_node = self.map_nodes[source_table]
        target_node = self.map_nodes[target_table]
        source_port = source_node["ports"][col_name]["right"]
        target_ports = list(target_node["ports"].values())
        target_port = target_ports[0]["left"]

        offset_y = 50 * self.zoom_level
        return (
            source_port[0], source_port[1],
            source_port[0] + 30 * self.zoom_level, source_port[1] + offset_y,
            target_port[0] - 30 * self.zoom_level, target_port[1] - offset_y,
            target_port[0], target_port[1],
        )

    def _draw_connection(self, source_table, target_table, col_name, color):
        coords = self._connection_points(source_table, col_name, target_table)
        item = self.canvas.create_line(
            *coords,
            fill=color,
            arrow="last",
            width=max(1, int(2 * self.zoom_level)),
            smooth=True,
            tags=("connection", f"fk_{source_table}_{target_table}")
        )
        conn = {"item": item, "source": source_table, "target": target_table, "col": col_name, "color": color}
        self.canvas.tag_bind(item, "<Enter>", lambda e, c=conn: self._highlight_connection(c))
        self.canvas.tag_bind(item, "<Leave>", lambda e: self._clear_highlight())
        return conn

    # --- ARRASTRE DE NODOS ---
    def _start_node_drag(self, event, table):
        self._drag_state = {
            "table": table,
            "last_x": self.canvas.canvasx(event.x),
            "last_y": self.canvas.canvasy(event.y),
        }
        self.canvas.tag_raise(table)

    def _do_node_drag(self, event, table):
        if not self._drag_state or self._drag_state.get("table") != table:
            return
        node = self.map_nodes.get(table)
        if not node:
            return

        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        dx = cur_x - self._drag_state["last_x"]
        dy = cur_y - self._drag_state["last_y"]
        if dx == 0 and dy == 0:
            return
        self._drag_state["last_x"] = cur_x
        self._drag_state["last_y"] = cur_y

        # Mover todos los elementos visuales del nodo de una (rápido: una
        # sola llamada a move() por el tag del grupo, no por item).
        self.canvas.move(table, dx, dy)

        node["x"] += dx
        node["y"] += dy
        for port in node["ports"].values():
            lx, ly = port["left"]
            rx, ry = port["right"]
            port["left"] = (lx + dx, ly + dy)
            port["right"] = (rx + dx, ry + dy)

        # Redibujar en vivo solo las conexiones que tocan este nodo (no
        # todo el mapa) - así el arrastre se siente fluido aunque haya
        # muchas tablas.
        for conn in self.map_node_connections.get(table, []):
            new_coords = self._connection_points(conn["source"], conn["col"], conn["target"])
            self.canvas.coords(conn["item"], *new_coords)

    def _end_node_drag(self, event, table):
        if not self._drag_state or self._drag_state.get("table") != table:
            return
        self._drag_state = None
        node = self.map_nodes.get(table)
        if not node or not self.current_db_name:
            return
        positions = self.history[self.current_db_name].setdefault("positions", {})
        positions[table] = {"x": node["x"], "y": node["y"]}
        save_json_history(self.storage_path, self.history)

    # --- RESALTADO POR HOVER (Focus Mode) ---
    def _highlight_connections(self, touching_items):
        for conn in self.map_connections:
            if conn["item"] in touching_items:
                self.canvas.itemconfig(conn["item"], fill=conn["color"], width=max(2, int(3 * self.zoom_level)))
                self.canvas.tag_raise(conn["item"])
            else:
                self.canvas.itemconfig(conn["item"], fill="#2a2a2a", width=1)

    def _highlight_node(self, table):
        touching = {c["item"] for c in self.map_node_connections.get(table, [])}
        if touching:
            self._highlight_connections(touching)

    def _highlight_connection(self, conn):
        self._highlight_connections({conn["item"]})

    def _clear_highlight(self):
        for conn in self.map_connections:
            self.canvas.itemconfig(conn["item"], fill=conn["color"], width=max(1, int(2 * self.zoom_level)))

    def _update_zoom_label(self):
        if hasattr(self, "zoom_pct_label"):
            self.zoom_pct_label.configure(text=f"{int(round(self.zoom_level * 100))}%")

    def update_zoom(self, v):
        self.zoom_level = float(v)
        self._update_zoom_label()
        self.render_map()

    def adjust_zoom(self, delta):
        """Botones [-]/[+] del toolbar del mapa."""
        self.zoom_level = max(0.1, min(2.5, self.zoom_level + delta))
        self.zoom_slider.set(self.zoom_level)
        self._update_zoom_label()
        self.render_map()

    def on_mouse_wheel(self, e):
        delta = 0.1 if e.delta > 0 else -0.1
        self.zoom_level = max(0.1, min(2.5, self.zoom_level + delta))
        self.zoom_slider.set(self.zoom_level)
        self._update_zoom_label()
        self.render_map()

    def auto_organize_map(self):
        """Descarta las posiciones manuales guardadas y vuelve a correr el
        algoritmo de distribución automática."""
        if not self.current_db_name:
            self.show_notification("Selecciona una base de datos primero", "warning")
            return
        self.history[self.current_db_name]["positions"] = {}
        save_json_history(self.storage_path, self.history)
        self.render_map()

    def toggle_theme(self):
        """Alterna entre tema oscuro y claro. El canvas del Mapa Relacional
        se mantiene siempre oscuro a propósito (es un diagrama, no un
        formulario - se lee mejor sobre fondo negro en cualquier tema)."""
        is_dark = ctk.get_appearance_mode() == "Dark"
        ctk.set_appearance_mode("light" if is_dark else "dark")
        self.theme_btn.configure(text="☀️" if is_dark else "🌙")

    def show_about(self):
        """Ventana 'Acerca de': logo, versión y link al repo."""
        win = ctk.CTkToplevel(self)
        win.title("Acerca de")
        win.geometry("420x420")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        if self.logo_path and os.path.exists(self.logo_path):
            logo_img = Image.open(self.logo_path)
            ratio = logo_img.height / logo_img.width
            w = 260
            logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(w, round(w * ratio)))
            ctk.CTkLabel(win, image=logo_ctk, text="").pack(pady=(25, 10))

        ctk.CTkLabel(win, text=f"Versión {APP_VERSION}", font=("Arial", 13, "bold")).pack(pady=(0, 10))
        ctk.CTkLabel(
            win,
            text=(
                "Herramienta de escritorio para mapear esquemas de bases de\n"
                "datos relacionales (SQL Server, PostgreSQL) y visualizar sus\n"
                "relaciones."
            ),
            justify="center",
        ).pack(pady=(0, 15), padx=20)

        ctk.CTkButton(
            win, text="Ver repositorio en GitHub",
            command=lambda: webbrowser.open(APP_REPO_URL),
            fg_color="#6f42c1",
        ).pack(pady=5)

        ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color="#5a6268").pack(pady=(20, 10))

    def show_help(self):
        """Ventana de ayuda con guía rápida de uso."""
        win = ctk.CTkToplevel(self)
        win.title("Ayuda")
        win.geometry("640x560")
        win.transient(self)
        win.grab_set()

        textbox = ctk.CTkTextbox(win, wrap="word", font=("Consolas", 12))
        textbox.pack(fill="both", expand=True, padx=15, pady=15)
        textbox.insert("1.0", HELP_TEXT)
        textbox.configure(state="disabled")

        ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color="#5a6268").pack(pady=(0, 15))

    def edit_uri(self):
        """Abre un prompt integrado para editar la URI (mostrado en el explorador)"""
        if not self.current_db_name:
            self.show_notification("Selecciona una base de datos primero", "warning")
            return
        
        # Cambiar al tab explorador
        self.tabs.set("🔍 Explorador")

        # Mostrar un panel editable en el explorador (se agregará en setup_explorer_tab)
        self.show_uri_editor()

    def show_uri_editor(self):
        """Muestra el panel para editar la URI de la base de datos seleccionada"""
        current_uri = self.history[self.current_db_name].get("uri", "")
        self.uri_edit_entry.delete(0, "end")
        self.uri_edit_entry.insert(0, current_uri)
        self.uri_editor_frame.pack(fill="x", padx=20, pady=(0, 5), after=self.exp_top)
        self.uri_edit_entry.focus()

    def hide_uri_editor(self):
        self.uri_editor_frame.pack_forget()

    def save_edited_uri(self):
        """Guarda la URI editada para la base de datos actual"""
        new_uri = self.uri_edit_entry.get().strip()
        if not new_uri:
            self.show_notification("La URI no puede estar vacía", "error")
            return
        self.save_history_entry(self.current_db_name, new_uri, status="pending")
        self.update_history_list()
        self.hide_uri_editor()
        self.show_notification("URI actualizada. Usa Refrescar para reconectar.", "success")

    def refresh_current(self):
        if self.current_db_name:
            uri = self.history[self.current_db_name].get("uri")
            self.start_scan_thread(uri, self.current_db_name)

    def draw_node(self, canvas, x, y, table_name, columns, fk_columns=None, node_id=None):
        """
        Dibuja un nodo de tabla en el canvas con header y lista de columnas.
        También registra el arrastre (drag & drop) y el resaltado por hover
        sobre el nodo completo (todos sus items comparten el tag node_id).

        Args:
            canvas: objeto Canvas de Tkinter
            x, y: coordenadas superiores izquierdas del nodo
            table_name: nombre de la tabla (str)
            columns: lista de dicts {"name","type","null","is_pk"(opcional)}
            fk_columns: set de nombres de columna que son Foreign Key
            node_id: ID único del nodo (por defecto usa table_name)

        Returns:
            dict con estructura:
            {
                "node_id": table_name,
                "x": x,
                "y": y,
                "width": width_total,
                "height": height_total,
                "ports": {
                    "column_name": {"left": (x_left, y_left), "right": (x_right, y_right)},
                    ...
                }
            }
        """
        if node_id is None:
            node_id = table_name
        fk_columns = fk_columns or set()

        # Configuración visual escalable
        zoom = self.zoom_level
        header_height = int(30 * zoom)
        row_height = int(20 * zoom)
        padding = int(8 * zoom)
        font_size_header = int(10 * zoom)
        font_size_field = int(9 * zoom)
        border_width = max(1, int(1 * zoom))

        # Colores (paleta moderna, coherente con la marca Etch-DB-Mapper)
        color_header = "#155e69"       # Teal oscuro (marca)
        color_header_border = "#0c3a41"
        color_field_bg = "#eef1f5"     # Gris muy claro, campo normal
        color_field_pk_bg = "#fff3cd"  # Dorado suave, Primary Key
        color_field_fk_bg = "#dbeeff"  # Celeste suave, Foreign Key
        color_border = "#2b7f8c"
        color_text = "#1a1a1a"
        color_port_pk = "#e0a800"
        color_port_fk = "#1e90ff"
        color_port_normal = "#5a6268"

        # Calcular dimensiones del nodo
        max_name_width = max(
            len(table_name) + 2,
            max((len(col.get("name", "")) + 3 for col in columns), default=0)
        )
        node_width = max(int(190 * zoom), int(20 + max_name_width * 7 * zoom))
        ports = {}

        # ========== HEADER (nombre de tabla) ==========
        header_rect = canvas.create_rectangle(
            x, y,
            x + node_width, y + header_height,
            fill=color_header,
            outline=color_header_border,
            width=border_width,
            tags=(node_id, "table_header")
        )

        header_text = canvas.create_text(
            x + node_width // 2,
            y + header_height // 2,
            text=f"▦ {table_name}",
            fill="white",
            font=("Arial", font_size_header, "bold"),
            tags=(node_id, "table_header_text")
        )

        # ========== CAMPOS (columnas) ==========
        field_y = y + header_height + padding

        for idx, col in enumerate(columns):
            col_name = col.get("name", "?")
            col_type = col.get("type", "")
            col_null = col.get("null", "YES")
            is_pk = bool(col.get("is_pk"))
            is_fk = col_name in fk_columns

            if is_pk:
                field_bg = color_field_pk_bg
                port_color = color_port_pk
            elif is_fk:
                field_bg = color_field_fk_bg
                port_color = color_port_fk
            else:
                field_bg = color_field_bg
                port_color = color_port_normal

            # Rectángulo del campo
            canvas.create_rectangle(
                x + padding, field_y,
                x + node_width - padding, field_y + row_height,
                fill=field_bg,
                outline=color_border,
                width=max(1, border_width - 1) if border_width > 1 else 1,
                tags=(node_id, f"field_{col_name}")
            )

            # Badge (🔑 PK, 🔗 FK) + nombre + tipo
            badge = "🔑 " if is_pk else ("🔗 " if is_fk else "")
            field_label = f"{badge}{col_name}: {col_type}"
            if col_null == "NO":
                field_label += " *"

            canvas.create_text(
                x + padding + 5,
                field_y + row_height // 2,
                text=field_label,
                fill=color_text,
                font=("Arial", font_size_field, "normal"),
                anchor="w",
                tags=(node_id, f"field_text_{col_name}")
            )

            # Coordenadas de puertos (left y right) para conexiones
            port_y = field_y + row_height // 2
            left_port = (x, port_y)
            right_port = (x + node_width, port_y)

            ports[col_name] = {
                "left": left_port,
                "right": right_port,
                "type": col_type,
                "nullable": col_null == "YES",
            }

            # Puntos de conexión visuales (círculos pequeños, color según rol)
            port_radius = max(2, int(3 * zoom))
            canvas.create_oval(
                left_port[0] - port_radius, left_port[1] - port_radius,
                left_port[0] + port_radius, left_port[1] + port_radius,
                fill=port_color,
                outline=port_color,
                tags=(node_id, f"port_left_{col_name}")
            )
            canvas.create_oval(
                right_port[0] - port_radius, right_port[1] - port_radius,
                right_port[0] + port_radius, right_port[1] + port_radius,
                fill=port_color,
                outline=port_color,
                tags=(node_id, f"port_right_{col_name}")
            )

            field_y += row_height

        # Rectángulo exterior del nodo (marco)
        canvas.create_rectangle(
            x, y,
            x + node_width, field_y + padding,
            outline=color_border,
            width=border_width,
            fill="",
            tags=(node_id, "table_outline")
        )

        # Arrastre (drag & drop) - agarra desde cualquier parte del nodo
        canvas.tag_bind(node_id, "<ButtonPress-1>", lambda e, t=table_name: self._start_node_drag(e, t))
        canvas.tag_bind(node_id, "<B1-Motion>", lambda e, t=table_name: self._do_node_drag(e, t))
        canvas.tag_bind(node_id, "<ButtonRelease-1>", lambda e, t=table_name: self._end_node_drag(e, t))

        # Resaltado por hover (Focus Mode)
        canvas.tag_bind(node_id, "<Enter>", lambda e, t=table_name: self._highlight_node(t))
        canvas.tag_bind(node_id, "<Leave>", lambda e: self._clear_highlight())

        # Cambiar el cursor sobre el nodo para indicar que se puede arrastrar
        canvas.tag_bind(node_id, "<Enter>", lambda e: canvas.configure(cursor="fleur"), add="+")
        canvas.tag_bind(node_id, "<Leave>", lambda e: canvas.configure(cursor=""), add="+")

        # Retornar información del nodo para mapeo y conectividad
        return {
            "node_id": node_id,
            "table_name": table_name,
            "x": x,
            "y": y,
            "width": node_width,
            "height": field_y + padding - y,
            "ports": ports,
            "canvas_objects": {
                "header_rect": header_rect,
                "header_text": header_text
            }
        }