"""
Janela principal do YouTube Clipper.
Interface gráfica com customtkinter.
"""

import os
import re
import threading
import tempfile
from tkinter import filedialog
from io import BytesIO

import customtkinter as ctk
import tkinter as tk
import urllib.request
from PIL import Image
from yt_dlp.utils import DownloadCancelled

from core.downloader import (
    is_valid_youtube_url,
    fetch_video_info,
    download_video,
    _format_download_error,
)
from core.cutter import check_ffmpeg_available, download_ffmpeg, cut_video
from core.processes import ProcessingCancelled, cleanup_for_dir


# Configuração do customtkinter
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')


def _sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos de nomes de arquivo Windows."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name[:200] if name else 'video'


def _format_duration(seconds: int) -> str:
    """Converte segundos para MM:SS ou HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


def _parse_time(time_str: str) -> float:
    """Converte HH:MM:SS ou MM:SS para segundos."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    else:
        return float(parts[0])


# ──────────────────────────────────────────────────────────────
#  RANGE SLIDER CUSTOM (Canvas com duas bolinhas arrastáveis)
# ──────────────────────────────────────────────────────────────

class RangeSliderCanvas(ctk.CTkFrame):
    """
    Widget de range slider com duas bolinhas arrastáveis.
    Opera em valores reais (from_..to) em segundos.
    Callback: command(start_value, end_value)
    """

    HANDLE_R = 8
    TRACK_H = 4
    CANVAS_H = 36
    PAD_X = 14

    def __init__(
        self,
        master,
        from_: float = 0,
        to: float = 600,
        command=None,
        **kwargs,
    ):
        super().__init__(master, fg_color='transparent', **kwargs)

        self._from = from_
        self._to = to if to > from_ else from_ + 1
        self._start_val = from_
        self._end_val = self._to
        self._command = command
        self._dragging = None  # 'start', 'end', ou None

        # Canvas
        self.canvas = tk.Canvas(
            self,
            height=self.CANVAS_H,
            highlightthickness=0,
            bg='#2b2b2b',
        )
        self.canvas.pack(fill='x', padx=4)

        # Desenhar trilha e handles
        self._draw_track()

        # Redesenhar ao redimensionar a janela
        self.canvas.bind('<Configure>', lambda e: self._redraw())

        # Eventos de mouse
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)

    def configure(self, **kwargs):
        if 'from_' in kwargs:
            self._from = kwargs.pop('from_')
        if 'to' in kwargs:
            self._to = kwargs.pop('to')
        if self._to <= self._from:
            self._to = self._from + 1
        if 'start_value' in kwargs:
            self._start_val = kwargs.pop('start_value')
        if 'end_value' in kwargs:
            self._end_val = kwargs.pop('end_value')
        super().configure(**kwargs)
        self._redraw()

    def set(self, start_val: float = None, end_val: float = None):
        """Define os valores do range."""
        if start_val is not None:
            self._start_val = max(self._from, min(start_val, self._to))
        if end_val is not None:
            self._end_val = max(self._from, min(end_val, self._to))
        if self._start_val > self._end_val:
            self._start_val, self._end_val = self._end_val, self._start_val
        self._redraw()

    def get(self):
        """Retorna (start_value, end_value)."""
        return self._start_val, self._end_val

    # ── Drawing ────────────────────────────────────────────

    def _draw_track(self):
        """Desenha a trilha e as bolinhas."""
        self.canvas.delete('all')
        w = self.canvas.winfo_width()
        if w <= 1:
            w = 400

        pad = self.PAD_X
        track_y = self.CANVAS_H // 2
        track_left = pad
        track_right = w - pad
        track_w = track_right - track_left

        # Fundo da trilha (cinza escuro)
        self.canvas.create_rectangle(
            track_left, track_y - self.TRACK_H,
            track_right, track_y + self.TRACK_H,
            fill='#555555', outline='', tags='track_bg',
        )

        # Faixa selecionada (azul)
        x_start = self._val_to_x(self._start_val, track_left, track_w)
        x_end = self._val_to_x(self._end_val, track_left, track_w)
        self.canvas.create_rectangle(
            x_start, track_y - self.TRACK_H,
            x_end, track_y + self.TRACK_H,
            fill='#1f6aa5', outline='', tags='track_sel',
        )

        # Handle início (azul claro)
        self.canvas.create_oval(
            x_start - self.HANDLE_R, track_y - self.HANDLE_R,
            x_start + self.HANDLE_R, track_y + self.HANDLE_R,
            fill='#3b8ed0', outline='white', width=2, tags='handle_start',
        )

        # Handle fim (verde)
        self.canvas.create_oval(
            x_end - self.HANDLE_R, track_y - self.HANDLE_R,
            x_end + self.HANDLE_R, track_y + self.HANDLE_R,
            fill='#45a65b', outline='white', width=2, tags='handle_end',
        )

    def _redraw(self):
        """Redesenha tudo e dispara callback."""
        self._draw_track()
        if self._command:
            self._command(self._start_val, self._end_val)

    # ── Conversão valor ↔ pixel ────────────────────────────

    def _val_to_x(self, val, track_left, track_w):
        if self._to == self._from:
            return track_left
        ratio = (val - self._from) / (self._to - self._from)
        return track_left + ratio * track_w

    def _x_to_val(self, x, track_left, track_w):
        if track_w <= 0:
            return self._from
        ratio = (x - track_left) / track_w
        ratio = max(0.0, min(1.0, ratio))
        return self._from + ratio * (self._to - self._from)

    # ── Snap para o step mais próximo (1 segundo) ──────────

    def _snap(self, val):
        """Arredonda para o inteiro mais próximo."""
        return round(val)

    # ── Mouse events ───────────────────────────────────────

    def _on_press(self, event):
        """Detecta qual handle está mais perto do clique."""
        w = self.canvas.winfo_width()
        pad = self.PAD_X
        track_left = pad
        track_w = w - 2 * pad
        track_y = self.CANVAS_H // 2

        x_start = self._val_to_x(self._start_val, track_left, track_w)
        x_end = self._val_to_x(self._end_val, track_left, track_w)

        dist_start = abs(event.x - x_start) + abs(event.y - track_y)
        dist_end = abs(event.x - x_end) + abs(event.y - track_y)

        # Zona de clique generosa
        threshold = self.HANDLE_R * 3
        if dist_start <= threshold and dist_start <= dist_end:
            self._dragging = 'start'
        elif dist_end <= threshold:
            self._dragging = 'end'
        else:
            # Clicou na trilha — move o handle mais perto
            val = self._snap(self._x_to_val(event.x, track_left, track_w))
            if abs(val - self._start_val) <= abs(val - self._end_val):
                self._start_val = min(val, self._end_val - 1)
                self._dragging = 'start'
            else:
                self._end_val = max(val, self._start_val + 1)
                self._dragging = 'end'
            self._redraw()

    def _on_drag(self, event):
        """Move o handle que está sendo arrastado."""
        if not self._dragging:
            return

        w = self.canvas.winfo_width()
        pad = self.PAD_X
        track_left = pad
        track_w = w - 2 * pad

        val = self._snap(self._x_to_val(event.x, track_left, track_w))

        if self._dragging == 'start':
            self._start_val = max(self._from, min(val, self._end_val - 1))
        elif self._dragging == 'end':
            self._end_val = min(self._to, max(val, self._start_val + 1))

        self._redraw()

    def _on_release(self, event):
        """Finaliza o arraste."""
        self._dragging = None


# ──────────────────────────────────────────────────────────────
#  JANELA PRINCIPAL
# ──────────────────────────────────────────────────────────────

class AppWindow(ctk.CTk):
    """Janela principal do aplicativo."""

    def __init__(self):
        super().__init__()

        self.title('YouTube Clipper')
        self.geometry('760x780')
        self.minsize(680, 520)
        self.resizable(True, True)

        # Estado
        self.video_info = None
        self.video_duration = 0
        self.is_processing = False
        self.cancel_event = None
        self._tmp_dir = None
        self._output_part = None
        self._bar_indeterminate = False

        self._build_ui()
        self._check_ffmpeg()
        self._fit_window_to_content()

        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _fit_window_to_content(self):
        """
        Ajusta a altura da janela para caber todo o conteúdo sem scroll,
        limitado ao tamanho da tela. Roda antes do mainloop, então não
        há 'piscada' de redimensionamento.
        """
        self.update_idletasks()
        content_h = self.scroll_frame.winfo_reqheight()
        # folgas: padding do scroll_frame (16 em cima + 16 embaixo) + barra de
        # título da janela (~38px) + margem de segurança
        margin = 16 + 16 + 38 + 14
        final_h = content_h + margin
        screen_h = self.winfo_screenheight()
        # deixa ~80px livres na tela (taskbar/outras janelas)
        max_h = screen_h - 80
        final_h = max(min(final_h, max_h), 520)
        self.geometry(f'760x{final_h}')

    def _build_ui(self):
        """Constrói todos os widgets da interface."""
        # Frame scrollável principal
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.scroll_frame.pack(fill='both', expand=True, padx=16, pady=16)

        # === TÍTULO ===
        ctk.CTkLabel(
            self.scroll_frame,
            text='YouTube Clipper',
            font=ctk.CTkFont(size=24, weight='bold'),
        ).pack(pady=(0, 12))

        # === SEÇÃO: URL ===
        url_frame = ctk.CTkFrame(self.scroll_frame)
        url_frame.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(url_frame, text='Link do YouTube:', anchor='w').pack(
            fill='x', padx=12, pady=(8, 2)
        )

        url_input_frame = ctk.CTkFrame(url_frame, fg_color='transparent')
        url_input_frame.pack(fill='x', padx=12, pady=(0, 8))

        self.url_entry = ctk.CTkEntry(
            url_input_frame,
            placeholder_text='https://www.youtube.com/watch?v=...',
            height=36,
        )
        self.url_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self.load_btn = ctk.CTkButton(
            url_input_frame,
            text='Carregar',
            width=90,
            height=36,
            command=self._load_video_info,
        )
        self.load_btn.pack(side='right')

        # === SEÇÃO: INFO DO VÍDEO ===
        self.info_frame = ctk.CTkFrame(self.scroll_frame)
        self.info_frame.pack(fill='x', pady=(0, 8))

        self.thumbnail_label = ctk.CTkLabel(
            self.info_frame, text='Thumbnail', width=160, height=90
        )
        self.thumbnail_label.pack(side='left', padx=12, pady=12)

        info_text_frame = ctk.CTkFrame(self.info_frame, fg_color='transparent')
        info_text_frame.pack(
            side='left', fill='both', expand=True, padx=(0, 12), pady=12
        )

        self.title_label = ctk.CTkLabel(
            info_text_frame,
            text='Título: —',
            font=ctk.CTkFont(size=13),
            anchor='w',
            wraplength=400,
        )
        self.title_label.pack(fill='x')

        self.duration_label = ctk.CTkLabel(
            info_text_frame, text='Duração: —', anchor='w'
        )
        self.duration_label.pack(fill='x')

        self.id_label = ctk.CTkLabel(
            info_text_frame, text='ID: —', anchor='w'
        )
        self.id_label.pack(fill='x')

        # === SEÇÃO: FORMATO ===
        format_frame = ctk.CTkFrame(self.scroll_frame)
        format_frame.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(format_frame, text='Formato de saída:', anchor='w').pack(
            fill='x', padx=12, pady=(8, 4)
        )

        self.format_var = ctk.StringVar(value='horizontal')

        format_btn_frame = ctk.CTkFrame(format_frame, fg_color='transparent')
        format_btn_frame.pack(fill='x', padx=12, pady=(0, 8))

        ctk.CTkRadioButton(
            format_btn_frame,
            text='Horizontal (1920×1080)',
            variable=self.format_var,
            value='horizontal',
        ).pack(side='left', padx=(0, 16))

        ctk.CTkRadioButton(
            format_btn_frame,
            text='Vertical (1080×1920)',
            variable=self.format_var,
            value='vertical',
        ).pack(side='left')

        # === SEÇÃO: TEMPO (RANGE SLIDER) ===
        time_frame = ctk.CTkFrame(self.scroll_frame)
        time_frame.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(time_frame, text='Intervalo de tempo:', anchor='w').pack(
            fill='x', padx=12, pady=(8, 4)
        )

        # Campos de texto de início/fim
        time_input_frame = ctk.CTkFrame(time_frame, fg_color='transparent')
        time_input_frame.pack(fill='x', padx=12, pady=(0, 4))

        ctk.CTkLabel(time_input_frame, text='Início:').pack(side='left')
        self.start_entry = ctk.CTkEntry(
            time_input_frame, width=100, placeholder_text='00:00:00'
        )
        self.start_entry.pack(side='left', padx=(4, 16))
        self.start_entry.insert(0, '00:00:00')
        self.start_entry.bind('<FocusOut>', lambda e: self._on_entry_change())
        self.start_entry.bind('<Return>', lambda e: self._on_entry_change())

        ctk.CTkLabel(time_input_frame, text='Fim:').pack(side='left')
        self.end_entry = ctk.CTkEntry(
            time_input_frame, width=100, placeholder_text='00:00:00'
        )
        self.end_entry.pack(side='left', padx=(4, 0))
        self.end_entry.bind('<FocusOut>', lambda e: self._on_entry_change())
        self.end_entry.bind('<Return>', lambda e: self._on_entry_change())

        # Range slider customizado (uma trilha, duas bolinhas)
        self.range_slider = RangeSliderCanvas(
            time_frame,
            from_=0,
            to=600,
            command=self._on_range_slider_change,
        )
        self.range_slider.pack(fill='x', padx=12, pady=(4, 4))

        self.clip_duration_label = ctk.CTkLabel(
            time_frame, text='Duração do trecho: 00:00', anchor='w'
        )
        self.clip_duration_label.pack(fill='x', padx=12, pady=(0, 8))

        # === SEÇÃO: PASTA ===
        folder_frame = ctk.CTkFrame(self.scroll_frame)
        folder_frame.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(folder_frame, text='Pasta de salvamento:', anchor='w').pack(
            fill='x', padx=12, pady=(8, 4)
        )

        folder_input_frame = ctk.CTkFrame(folder_frame, fg_color='transparent')
        folder_input_frame.pack(fill='x', padx=12, pady=(0, 4))

        self.folder_entry = ctk.CTkEntry(
            folder_input_frame,
            placeholder_text='Selecione uma pasta...',
        )
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))

        ctk.CTkButton(
            folder_input_frame,
            text='Selecionar',
            width=100,
            command=self._select_folder,
        ).pack(side='right')

        name_frame = ctk.CTkFrame(folder_frame, fg_color='transparent')
        name_frame.pack(fill='x', padx=12, pady=(0, 8))

        ctk.CTkLabel(name_frame, text='Nome do arquivo:').pack(side='left')
        self.filename_entry = ctk.CTkEntry(
            name_frame, placeholder_text=' nome_personalizado'
        )
        self.filename_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))

        # === SEÇÃO: PROGRESSO ===
        progress_frame = ctk.CTkFrame(self.scroll_frame)
        progress_frame.pack(fill='x', pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill='x', padx=12, pady=(8, 4))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            progress_frame, text='Pronto', anchor='w'
        )
        self.status_label.pack(fill='x', padx=12, pady=(0, 8))

        # === SEÇÃO: BOTÕES ===
        btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color='transparent')
        btn_frame.pack(fill='x')

        self.process_btn = ctk.CTkButton(
            btn_frame,
            text='Processar',
            height=40,
            font=ctk.CTkFont(size=15, weight='bold'),
            command=self._start_processing,
        )
        self.process_btn.pack(side='left', expand=True, fill='x', padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text='Cancelar',
            height=40,
            fg_color='#b33a3a',
            hover_color='#8f2e2e',
            command=self._cancel_processing,
            state='disabled',
        )
        self.cancel_btn.pack(side='left', fill='x', padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            btn_frame,
            text='Abrir Pasta',
            height=40,
            command=self._open_output_folder,
            state='disabled',
        )
        self.open_folder_btn.pack(side='right', expand=True, fill='x')

        self._output_folder = ''

    # ── Callbacks do range slider ──────────────────────────

    def _on_range_slider_change(self, start_val, end_val):
        """Chamado quando o range slider muda (valores em segundos)."""
        self.start_entry.delete(0, 'end')
        self.start_entry.insert(0, _format_duration(int(start_val)))
        self.end_entry.delete(0, 'end')
        self.end_entry.insert(0, _format_duration(int(end_val)))
        self._update_clip_duration()

    def _on_entry_change(self):
        """Chamado quando o usuário digita nos campos de tempo manualmente."""
        try:
            start = _parse_time(self.start_entry.get())
            end = _parse_time(self.end_entry.get())
            if self.video_duration > 0:
                self.range_slider.set(start_val=start, end_val=end)
        except (ValueError, IndexError):
            pass

    def _update_clip_duration(self):
        """Atualiza o label de duração do trecho."""
        try:
            start, end = self.range_slider.get()
            duration = max(0, end - start)
            self.clip_duration_label.configure(
                text=f'Duração do trecho: {_format_duration(int(duration))}'
            )
        except (ValueError, IndexError):
            pass

    # ── Outros callbacks ───────────────────────────────────

    def _check_ffmpeg(self):
        """Verifica se o ffmpeg está disponível. Baixa automaticamente se não."""
        if check_ffmpeg_available():
            return

        # Não encontrado — tentar baixar automaticamente em thread separada
        self.process_btn.configure(state='disabled')
        self.status_label.configure(
            text='FFmpeg não encontrado. Baixando automaticamente...',
            text_color='orange',
        )

        def _download():
            def _progress(pct, msg):
                self.after(0, lambda: self._update_progress(pct, msg))

            success = download_ffmpeg(_progress)

            if success and check_ffmpeg_available():
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text='FFmpeg instalado com sucesso! Pronto para usar.',
                        text_color='green',
                    ),
                )
                self.after(0, lambda: self.process_btn.configure(state='normal'))
            else:
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text=(
                            'Não foi possível baixar o ffmpeg automaticamente. '
                            'Baixe manualmente em https://www.gyan.dev/ffmpeg/builds/ '
                            'e coloque ffmpeg.exe e ffprobe.exe na pasta assets/ ou '
                            'adicione ao PATH.'
                        ),
                        text_color='red',
                    ),
                )
                self.after(0, lambda: self.progress_bar.set(0))

        threading.Thread(target=_download, daemon=True).start()

    def _select_folder(self):
        """Abre o seletor de diretório."""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, 'end')
            self.folder_entry.insert(0, folder)
            self._output_folder = folder

    def _load_video_info(self):
        """Carrega informações do vídeo em thread separada."""
        url = self.url_entry.get().strip()
        if not is_valid_youtube_url(url):
            self.status_label.configure(
                text='Link do YouTube inválido!', text_color='red'
            )
            return

        self.load_btn.configure(state='disabled')
        self.status_label.configure(
            text='Carregando informações...', text_color='white'
        )

        def _fetch():
            try:
                info = fetch_video_info(url)
                self.after(0, lambda: self._display_video_info(info))
            except Exception as e:
                err_msg = _format_download_error(e)
                self.after(
                    0,
                    lambda msg=err_msg: self.status_label.configure(
                        text=f'Erro: {msg}', text_color='red'
                    ),
                )
            finally:
                self.after(0, lambda: self.load_btn.configure(state='normal'))

        threading.Thread(target=_fetch, daemon=True).start()

    def _display_video_info(self, info: dict):
        """Exibe as informações do vídeo na interface."""
        self.video_info = info
        self.video_duration = info['duration']

        self.title_label.configure(text=f'Título: {info["title"]}')
        self.duration_label.configure(
            text=f'Duração: {_format_duration(info["duration"])}'
        )
        self.id_label.configure(text=f'ID: {info["id"]}')

        # Configurar range slider com a duração real do vídeo
        self.range_slider.configure(
            to=self.video_duration,
            start_value=0,
            end_value=self.video_duration,
        )

        safe_name = _sanitize_filename(info['title'])
        self.filename_entry.delete(0, 'end')
        self.filename_entry.insert(0, safe_name)

        if not self.folder_entry.get().strip():
            default_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
            self.folder_entry.delete(0, 'end')
            self.folder_entry.insert(0, default_folder)
            self._output_folder = default_folder

        self._update_clip_duration()
        self.status_label.configure(
            text='Vídeo carregado com sucesso!', text_color='green'
        )

        thumb_url = info.get('thumbnail_url', '')
        if thumb_url:
            threading.Thread(
                target=self._load_thumbnail, args=(thumb_url,), daemon=True
            ).start()

    def _load_thumbnail(self, url: str):
        """Carrega e exibe a miniatura do vídeo."""
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
            img = Image.open(BytesIO(data))
            img = img.resize((160, 90), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img, size=(160, 90)
            )
            self.after(
                0, lambda: self.thumbnail_label.configure(image=ctk_img, text='')
            )
        except Exception:
            pass

    def _validate_inputs(self) -> str:
        """Valida todas as entradas. Retorna mensagem de erro ou None."""
        if not self.video_info:
            return 'Carregue as informações do vídeo primeiro.'

        url = self.url_entry.get().strip()
        if not is_valid_youtube_url(url):
            return 'Link do YouTube inválido.'

        folder = self.folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            return 'Selecione uma pasta de salvamento válida.'

        filename = self.filename_entry.get().strip()
        if not filename:
            return 'Informe um nome para o arquivo.'

        try:
            start = _parse_time(self.start_entry.get())
        except (ValueError, IndexError):
            return 'Formato de tempo de início inválido (use HH:MM:SS).'

        try:
            end = _parse_time(self.end_entry.get())
        except (ValueError, IndexError):
            return 'Formato de tempo de fim inválido (use HH:MM:SS).'

        if end <= start:
            return 'O tempo final deve ser maior que o inicial.'

        if end > self.video_duration:
            return (
                f'O tempo final ({_format_duration(int(end))}) excede a '
                f'duração do vídeo ({_format_duration(self.video_duration)}).'
            )

        return None

    def _start_processing(self):
        """Inicia o pipeline de processamento."""
        error = self._validate_inputs()
        if error:
            self.status_label.configure(text=error, text_color='red')
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.cancel_event = threading.Event()
        self.process_btn.configure(state='disabled')
        self.open_folder_btn.configure(state='disabled')
        self.cancel_btn.configure(state='normal')

        url = self.url_entry.get().strip()
        folder = self.folder_entry.get().strip()
        filename = _sanitize_filename(self.filename_entry.get().strip())
        target_format = self.format_var.get()
        start_time = _parse_time(self.start_entry.get())
        end_time = _parse_time(self.end_entry.get())

        self._output_folder = folder

        def _progress(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))

        def _worker():
            output_path = None
            tmp_dir = tempfile.mkdtemp(prefix='ytclip_')
            self._tmp_dir = tmp_dir
            try:
                clip_len = end_time - start_time
                output_name = f'{filename}_cortado'
                output_path = os.path.join(folder, f'{output_name}.mp4')
                # Arquivo parcial (deve sumir em erro/cancelamento/fechamento)
                self._output_part = output_path + '.part.mp4'

                _progress(0, 'Baixando vídeo...')
                video_path = download_video(
                    url, tmp_dir, filename, _progress, start_time, end_time,
                    self.cancel_event,
                )

                _progress(0, 'Cortando vídeo...')
                cut_video(
                    video_path, output_path, start_time, end_time,
                    target_format, _progress, self.cancel_event,
                )

                _progress(100, 'Concluído com sucesso!')
                self.after(0, self._processing_done)

            except (ProcessingCancelled, DownloadCancelled):
                if output_path and os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                if self._output_part and os.path.exists(self._output_part):
                    try:
                        os.remove(self._output_part)
                    except OSError:
                        pass
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text='Processamento cancelado.', text_color='orange'
                    ),
                )
                self.after(0, self._processing_reset)
            except Exception as e:
                if output_path and os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                if self._output_part and os.path.exists(self._output_part):
                    try:
                        os.remove(self._output_part)
                    except OSError:
                        pass
                err_msg = _format_download_error(e)[:150]
                self.after(
                    0,
                    lambda msg=err_msg: self.status_label.configure(
                        text=f'Erro: {msg}', text_color='red'
                    ),
                )
                self.after(0, self._processing_reset)
            finally:
                cleanup_for_dir(tmp_dir)
                self._tmp_dir = None

        threading.Thread(target=_worker, daemon=True).start()

    def _cancel_processing(self):
        """Cancela o processamento em andamento."""
        if not self.is_processing:
            return
        self.cancel_btn.configure(state='disabled')
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.status_label.configure(
            text='Cancelando... (aguarde a limpeza)', text_color='orange'
        )

    def _on_close(self):
        """Fecha a janela garantindo que nenhum subprocesso fique órfão."""
        if self.is_processing:
            if self.cancel_event is not None:
                self.cancel_event.set()
            cleanup_for_dir(self._tmp_dir)
            if self._output_part and os.path.exists(self._output_part):
                try:
                    os.remove(self._output_part)
                except OSError:
                    pass
        self.destroy()

    def _stop_indeterminate(self):
        if self._bar_indeterminate:
            try:
                self.progress_bar.stop()
                self.progress_bar.configure(mode='determinate')
            except Exception:
                pass
            self._bar_indeterminate = False

    def _update_progress(self, pct: float, msg: str):
        """Atualiza barra de progresso e status."""
        if pct is not None and pct < 0:
            # Modo indeterminado: barra pulsando (total desconhecido)
            if not self._bar_indeterminate:
                try:
                    self.progress_bar.configure(mode='indeterminate')
                    self.progress_bar.start()
                except Exception:
                    pass
                self._bar_indeterminate = True
        else:
            if self._bar_indeterminate:
                self._stop_indeterminate()
            if pct is not None:
                self.progress_bar.set(pct / 100)
        self.status_label.configure(text=msg, text_color='white')

    def _processing_done(self):
        """Chamado quando o processamento termina com sucesso."""
        self.is_processing = False
        self.cancel_event = None
        self._stop_indeterminate()
        self.progress_bar.set(1)
        self.process_btn.configure(state='normal')
        self.open_folder_btn.configure(state='normal')
        self.cancel_btn.configure(state='disabled')
        self.status_label.configure(
            text='Concluído com sucesso!', text_color='green'
        )

    def _processing_reset(self):
        """Reseta o estado após erro/cancelamento."""
        self.is_processing = False
        self.cancel_event = None
        self._stop_indeterminate()
        self.progress_bar.set(0)
        self.process_btn.configure(state='normal')
        self.cancel_btn.configure(state='disabled')

    def _open_output_folder(self):
        """Abre a pasta de saída no Explorer."""
        if self._output_folder and os.path.isdir(self._output_folder):
            os.startfile(self._output_folder)
