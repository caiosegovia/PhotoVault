import threading
import time
import logging
import customtkinter as ctk
from pathlib import Path
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, COLOR_BORDER, FONT_FAMILY, FONT_SIZE_TITLE, 
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count, format_speed, format_eta

logger = logging.getLogger(__name__)

def _record_to_index(ops, destination) -> None:
    """Record newly copied files into destination_index."""
    try:
        from core.database import bulk_save_destination_records
        records = []
        for op in ops:
            if op.status != 'done':
                continue
            try:
                stat = op.dst.stat()
                records.append({
                    'path': str(op.dst),
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'sha256': getattr(op, 'sha256', '') or '',
                })
            except OSError:
                pass
        if records:
            bulk_save_destination_records(str(destination), records)
            logger.info(f"Indexed {len(records)} files to destination cache.")
    except Exception:
        logger.exception("Failed to record files to destination index")


class ProgressView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._running = False
        self._start_time = None
        self._processed = 0
        self._total = 0
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._log_lines = 0
        self._max_log_lines = 1000
        self._build()

    def _build(self):
        self.container = ctk.CTkFrame(self.parent, fg_color='transparent')
        self.container.pack(fill='both', expand=True, padx=30, pady=30)

        # Title section
        title_row = ctk.CTkFrame(self.container, fg_color='transparent')
        title_row.pack(fill='x', pady=(0, 24))
        
        ctk.CTkLabel(
            title_row, text='Execução da Organização',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left')

        # Progress Card
        prog_card = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        prog_card.pack(fill='x', pady=(0, 20))

        self.file_label = ctk.CTkLabel(
            prog_card, text='Pronto para iniciar a operação.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT,
            wraplength=800, anchor='w'
        )
        self.file_label.pack(anchor='w', padx=24, pady=(24, 8))

        self.progress_var = ctk.DoubleVar(value=0.0)
        self.main_progress = ctk.CTkProgressBar(
            prog_card, variable=self.progress_var,
            height=12, corner_radius=6,
            fg_color=COLOR_BG, progress_color=COLOR_ACCENT
        )
        self.main_progress.pack(fill='x', padx=24, pady=8)

        self.progress_label = ctk.CTkLabel(
            prog_card, text='0 / 0',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_TEXT_DIM
        )
        self.progress_label.pack(anchor='e', padx=24, pady=(0, 12))

        # Stats Grid
        stats_frame = ctk.CTkFrame(prog_card, fg_color='transparent')
        stats_frame.pack(fill='x', padx=24, pady=(0, 24))

        self.speed_label = ctk.CTkLabel(stats_frame, text='Velocidade: —', font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM)
        self.speed_label.pack(side='left', padx=(0, 32))

        self.eta_label = ctk.CTkLabel(stats_frame, text='ETA: —', font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM)
        self.eta_label.pack(side='left', padx=(0, 32))

        self.copied_label = ctk.CTkLabel(stats_frame, text='Copiado: 0 B', font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM)
        self.copied_label.pack(side='left')

        # Controls
        ctrl_row = ctk.CTkFrame(self.container, fg_color='transparent')
        ctrl_row.pack(fill='x', pady=(0, 20))

        self.start_btn = ctk.CTkButton(
            ctrl_row, text='▶  Iniciar Operação',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_SUCCESS, hover_color='#059669',
            corner_radius=10, height=48, width=200,
            command=self._start
        )
        self.start_btn.pack(side='left', padx=(0, 12))

        self.pause_btn = ctk.CTkButton(
            ctrl_row, text='⏸  Pausar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_WARNING, hover_color='#d97706',
            corner_radius=10, height=48, width=140,
            command=self._toggle_pause, state='disabled'
        )
        self.pause_btn.pack(side='left', padx=(0, 12))

        self.cancel_btn = ctk.CTkButton(
            ctrl_row, text='✕  Cancelar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ERROR, hover_color='#dc2626',
            corner_radius=10, height=48, width=140,
            command=self._cancel, state='disabled'
        )
        self.cancel_btn.pack(side='left')

        self.back_btn = ctk.CTkButton(
            ctrl_row, text='◀  Voltar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', border_color=COLOR_BORDER, border_width=1,
            corner_radius=10, height=48, width=140,
            command=lambda: self.main_window.navigate('duplicates')
        )
        self.back_btn.pack(side='right')

        # Configuration (Workers/Verify)
        config_frame = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=12, border_color=COLOR_BORDER, border_width=1)
        config_frame.pack(fill='x', pady=(0, 20))
        
        inner_config = ctk.CTkFrame(config_frame, fg_color='transparent')
        inner_config.pack(padx=20, pady=12, fill='x')

        ctk.CTkLabel(inner_config, text='Threads (Paralelismo):', font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM).pack(side='left', padx=(0, 12))
        self.workers_btn = ctk.CTkSegmentedButton(
            inner_config, values=['1', '2', '4', '8', '16'],
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            selected_color=COLOR_ACCENT, fg_color=COLOR_BG,
            width=250, height=32
        )
        self.workers_btn.set('8')
        self.workers_btn.pack(side='left', padx=(0, 40))

        self.verify_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            inner_config, text='Verificar integridade (SHA-256)',
            variable=self.verify_var, font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2, border_color=COLOR_BORDER
        ).pack(side='left')

        # Log Section
        log_header = ctk.CTkFrame(self.container, fg_color='transparent')
        log_header.pack(fill='x', pady=(10, 8))
        ctk.CTkLabel(log_header, text='Log de Operações', font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT).pack(side='left')
        
        self.log_text = ctk.CTkTextbox(
            self.container, font=("Consolas" if __import__('platform').system() == 'Windows' else "Monospace", 11),
            fg_color='#0a0b14', text_color='#d1d5db',
            corner_radius=12, border_color=COLOR_BORDER, border_width=1
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.configure(state='disabled')

    def _log(self, msg: str, level=logging.INFO):
        # Limit lines in text widget to prevent memory leak / lag
        self.log_text.configure(state='normal')
        if self._log_lines >= self._max_log_lines:
            self.log_text.delete('1.0', '2.0')
        else:
            self._log_lines += 1
            
        self.log_text.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        
        if level == logging.ERROR:
            logger.error(msg)
        else:
            logger.info(msg)

    def _start(self):
        plan = self.app.app_state.get('plan')
        if not plan:
            self._log('Erro: Nenhum plano de organização disponível.', logging.ERROR)
            return

        if self._running: return

        workers = int(self.workers_btn.get())
        verify = self.verify_var.get()

        self._running = True
        self._pause_event.set()
        self._stop_event.clear()
        self._processed = 0
        self._total = len(plan.operations)
        self._start_time = time.time()
        self._copied_bytes = 0
        self._log_lines = 0

        self.start_btn.configure(state='disabled')
        self.pause_btn.configure(state='normal')
        self.cancel_btn.configure(state='normal')
        self.back_btn.configure(state='disabled')
        self.workers_btn.configure(state='disabled')
        self.progress_var.set(0)
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

        mode = self.app.app_state.get('mode', 'copy').upper()
        self._log(f'INICIANDO OPERAÇÃO: {mode}')
        self._log(f'Total de arquivos: {self._total}')
        self._log(f'Paralelismo: {workers} workers | Verificação: {"Ativa" if verify else "Desativa"}')

        self._bytes_lock = threading.Lock()
        
        _last_ui_update = [0.0]

        def worker():
            try:
                from core.organizer import execute_plan

                def cb(current, total, src, op):
                    if self._stop_event.is_set(): return

                    processed = current + 1
                    self._processed = processed

                    size = getattr(op, '_pre_size', 0)
                    with self._bytes_lock:
                        self._copied_bytes += size
                        copied = self._copied_bytes

                    now = time.monotonic()
                    if now - _last_ui_update[0] < 0.1 and processed < total:
                        return
                    _last_ui_update[0] = now

                    elapsed = time.time() - self._start_time
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining = total - processed
                    progress = processed / total if total > 0 else 0

                    self.parent.after(0, lambda p=progress, c=processed, t=total, s=src, sp=speed, r=remaining, cb=copied:
                                      self._update_ui(p, c, t, s, sp, r, cb))

                result = execute_plan(
                    plan, callback=cb, workers=workers, verify=verify,
                    pause_event=self._pause_event, stop_event=self._stop_event,
                )
                self.app.app_state['exec_result'] = result
                self.parent.after(0, self._on_done)
            except Exception as e:
                logger.exception("Fatal error during execution plan")
                self.parent.after(0, lambda m=str(e): self._on_worker_error(m))

        threading.Thread(target=worker, daemon=True).start()

    def _update_ui(self, progress, current, total, src, speed, remaining, copied):
        self.progress_var.set(progress)
        self.progress_label.configure(text=f'{format_count(current)} / {format_count(total)}')
        self.file_label.configure(text=f'Processando: {src.name}')
        self.speed_label.configure(text=f'Velocidade: {format_speed(speed)}')
        self.eta_label.configure(text=format_eta(remaining, speed))
        self.copied_label.configure(text=f'Copiado: {format_size(copied)}')
        self._log(f'OK: {src.name}')

    def _on_worker_error(self, msg: str):
        self._running = False
        self._log(f'ERRO FATAL: {msg}', logging.ERROR)
        self.start_btn.configure(state='normal', text='▶  Reintentar')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        self.back_btn.configure(state='normal')
        self.workers_btn.configure(state='normal')

    def _on_done(self):
        self._running = False
        result = self.app.app_state.get('exec_result')
        elapsed = time.time() - self._start_time
        
        self._log(f'OPERAÇÃO CONCLUÍDA em {elapsed:.1f}s')
        if result:
            self._log(f'Sucesso: {result.processed} | Erros: {result.errors} | Ignorados: {result.skipped}')

        self.start_btn.configure(state='normal', text='✓ Concluído')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        self.back_btn.configure(state='normal')
        self.workers_btn.configure(state='normal')
        self.progress_var.set(1.0)

        self._save_session('completed')

        # Background indexing
        plan = self.app.app_state.get('plan')
        if plan:
            self.app.executor.submit(_record_to_index, plan.operations, plan.destination)

        self.parent.after(1500, lambda: self.main_window.navigate('report'))

    def _save_session(self, status: str = 'completed') -> None:
        from datetime import datetime
        from core.database import save_session
        result = self.app.app_state.get('exec_result')
        dup = self.app.app_state.get('dup_result')
        try:
            save_session({
                'started_at': datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else None,
                'completed_at': datetime.now().isoformat(),
                'sources': [s['path'] for s in self.app.app_state.get('sources', [])],
                'destination': str(self.app.app_state.get('destination', '')),
                'files_processed': result.processed if result else self._processed,
                'files_moved': result.processed if result else self._processed,
                'duplicates_found': len(dup.exact) + len(dup.visual) if dup else 0,
                'space_freed': dup.space_wasted if dup else 0,
                'errors': result.errors if result else 0,
                'total_files': result.total if result else self._total,
                'status': status,
            })
        except Exception:
            logger.exception("Failed to save session to database")

    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_btn.configure(text='▶  Retomar', fg_color=COLOR_SUCCESS)
            self._log('OPERAÇÃO PAUSADA')
        else:
            self._pause_event.set()
            self.pause_btn.configure(text='⏸  Pausar', fg_color=COLOR_WARNING)
            self._log('REPRODUZINDO...')

    def _cancel(self):
        self._running = False
        self._stop_event.set()
        self._pause_event.set()
        self._log('OPERAÇÃO CANCELADA PELO USUÁRIO', logging.WARNING)
        self.start_btn.configure(state='normal', text='▶  Iniciar')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        self.back_btn.configure(state='normal')
        self.workers_btn.configure(state='normal')
        if self._start_time:
            self._save_session('cancelled')

    def refresh(self):
        if not self._running:
            self.start_btn.configure(state='normal', text='▶  Iniciar Operação')
            self.progress_var.set(0)
            self.progress_label.configure(text='0 / 0')
            self.file_label.configure(text='Pronto para iniciar a operação.')
            self.log_text.configure(state='normal')
            self.log_text.delete('1.0', 'end')
            self.log_text.configure(state='disabled')
