import threading
import time
import customtkinter as ctk
from pathlib import Path
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count, format_speed, format_eta


def _record_to_index(ops, destination) -> None:
    """Record newly copied files into destination_index (best-effort, runs in daemon thread)."""
    try:
        from core.organizer import _hash_file
        from core.database import bulk_save_destination_records
        records = []
        for op in ops:
            if op.status != 'done':
                continue
            try:
                stat = op.dst.stat()
                sha256 = getattr(op, 'sha256', None)
                if not sha256:
                    sha256 = _hash_file(op.dst)
                records.append({
                    'path': str(op.dst),
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'sha256': sha256,
                })
            except OSError:
                pass
        if records:
            bulk_save_destination_records(str(destination), records)
    except Exception:
        pass  # index is best-effort, never block the UI


def _write_error_log(text: str) -> None:
    try:
        log_path = Path.home() / '.photovault' / 'error.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}]\n')
            f.write(text)
    except Exception:
        pass


class ProgressView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._running = False
        self._thread = None
        self._start_time = None
        self._processed = 0
        self._total = 0
        self._last_ui_update = 0.0
        self._log_lines = 0
        self._max_log_lines = 500
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = não pausado
        self._stop_event = threading.Event()
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            self.scroll, text='Executando Organização',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 20))

        # Progress card
        prog_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        prog_card.pack(fill='x', pady=(0, 14))

        # Current file label
        self.file_label = ctk.CTkLabel(
            prog_card, text='Pronto para executar.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM,
            wraplength=900, anchor='w'
        )
        self.file_label.pack(anchor='w', padx=20, pady=(16, 4))

        # Main progress bar
        self.progress_var = ctk.DoubleVar(value=0.0)
        self.main_progress = ctk.CTkProgressBar(
            prog_card, variable=self.progress_var,
            height=20, corner_radius=8,
            fg_color=COLOR_CARD, progress_color=COLOR_ACCENT
        )
        self.main_progress.pack(fill='x', padx=20, pady=4)

        self.progress_label = ctk.CTkLabel(
            prog_card, text='0 / 0',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self.progress_label.pack(anchor='e', padx=20, pady=(0, 4))

        # Stats row
        stats_row = ctk.CTkFrame(prog_card, fg_color='transparent')
        stats_row.pack(fill='x', padx=20, pady=(4, 16))

        self.speed_label = ctk.CTkLabel(
            stats_row, text='Velocidade: —',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self.speed_label.pack(side='left', padx=(0, 20))

        self.eta_label = ctk.CTkLabel(
            stats_row, text='ETA: —',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self.eta_label.pack(side='left', padx=(0, 20))

        self.copied_label = ctk.CTkLabel(
            stats_row, text='Copiado: 0 B',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self.copied_label.pack(side='left')

        # Control buttons
        ctrl = ctk.CTkFrame(self.scroll, fg_color='transparent')
        ctrl.pack(fill='x', pady=(0, 14))

        self.start_btn = ctk.CTkButton(
            ctrl, text='▶  Iniciar',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_SUCCESS, hover_color='#27ae60',
            corner_radius=8, height=44, width=140,
            command=self._start
        )
        self.start_btn.pack(side='left', padx=(0, 10))

        self.pause_btn = ctk.CTkButton(
            ctrl, text='⏸  Pausar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_WARNING, hover_color='#d68910',
            corner_radius=8, height=44, width=120,
            command=self._toggle_pause,
            state='disabled'
        )
        self.pause_btn.pack(side='left', padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            ctrl, text='✕  Cancelar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ERROR, hover_color='#c0392b',
            corner_radius=8, height=44, width=120,
            command=self._cancel,
            state='disabled'
        )
        self.cancel_btn.pack(side='left')

        # Settings row (workers + verify)
        settings = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=10)
        settings.pack(fill='x', pady=(0, 14))

        inner_s = ctk.CTkFrame(settings, fg_color='transparent')
        inner_s.pack(padx=16, pady=10, anchor='w')

        ctk.CTkLabel(
            inner_s, text='Workers:',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=(0, 8))

        self.workers_btn = ctk.CTkSegmentedButton(
            inner_s, values=['1', '2', '4', '8'],
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color=COLOR_BG, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT2,
            unselected_color=COLOR_BG, unselected_hover_color=COLOR_CARD,
            width=180, height=28
        )
        self.workers_btn.set('4')
        self.workers_btn.pack(side='left', padx=(0, 24))

        self.verify_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            inner_s, text='Verificar integridade (SHA-256)',
            variable=self.verify_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            checkmark_color=COLOR_TEXT
        ).pack(side='left')

        self._settings_frame = settings

        # Log area
        log_label = ctk.CTkLabel(
            self.scroll, text='Log em Tempo Real',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        )
        log_label.pack(anchor='w', pady=(10, 4))

        log_card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        log_card.pack(fill='x')

        self.log_text = ctk.CTkTextbox(
            log_card, height=250,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color=COLOR_BG, text_color=COLOR_TEXT,
            corner_radius=8
        )
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.log_text.configure(state='disabled')

    def _log(self, msg: str, color: str = None):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n')
        self._log_lines += msg.count('\n') + 1
        if self._log_lines > self._max_log_lines:
            excess = self._log_lines - self._max_log_lines
            self.log_text.delete('1.0', f'{excess + 1}.0')
            self._log_lines = self._max_log_lines
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _start(self):
        plan = self.app.app_state.get('plan')
        if not plan:
            self._log('Erro: nenhum plano gerado. Volte ao Preview.')
            return

        if self._running:
            return

        workers = int(self.workers_btn.get())
        verify = self.verify_var.get()
        is_ingest = self.app.app_state.get('plan_kind') == 'ingest'

        self._running = True
        self._pause_event.set()
        self._stop_event.clear()
        self._processed = 0
        self._total = len(plan.operations)
        self._start_time = time.time()
        self._last_ui_update = 0.0
        self._log_lines = 0
        self._copied_bytes = 0

        self.start_btn.configure(state='disabled')
        self.pause_btn.configure(state='normal')
        self.cancel_btn.configure(state='normal')
        try:
            self.workers_btn.configure(state='disabled')
            self._settings_frame.configure(fg_color=COLOR_BG)
        except Exception:
            pass
        self.progress_var.set(0)

        mode_txt = self.app.app_state.get('mode', 'copy')
        verify_txt = 'com verificação SHA-256' if verify else 'modo rápido'
        self._log(f'Iniciando {mode_txt} de {self._total} arquivos  •  {workers} worker(s)  •  {verify_txt}...')
        self._log(f'Destino: {self.app.app_state.get("destination")}')

        self._bytes_lock = threading.Lock()

        def worker():
            try:
                if is_ingest:
                    self._run_ingest_worker()
                    return

                from core.organizer import execute_plan

                def cb(current, total, src, op):
                    if self._stop_event.is_set():
                        return

                    processed = current + 1
                    self._processed = processed

                    size = getattr(op, '_pre_size', None)
                    if size is None:
                        try:
                            size = src.stat().st_size
                        except OSError:
                            try:
                                size = op.dst.stat().st_size
                            except OSError:
                                size = 0
                    with self._bytes_lock:
                        self._copied_bytes += size
                        copied = self._copied_bytes

                    elapsed = time.time() - self._start_time
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining = total - processed
                    progress = processed / total if total > 0 else 0
                    now = time.monotonic()
                    is_last = processed >= total
                    if not is_last and now - self._last_ui_update < 0.10:
                        return
                    self._last_ui_update = now

                    self.parent.after(0, lambda p=progress, c=processed, sp=speed,
                                               r=remaining, f=copied:
                                      self._update_ui(p, c, total, src, sp, r, f))

                result = execute_plan(
                    plan, callback=cb,
                    workers=workers, verify=verify,
                    pause_event=self._pause_event,
                    stop_event=self._stop_event,
                )
                self.app.app_state['exec_result'] = result
                self.parent.after(0, self._on_done)
            except Exception as e:
                import traceback
                _write_error_log(traceback.format_exc())
                self.parent.after(0, lambda msg=str(e): self._on_worker_error(msg))

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def _run_ingest_worker(self):
        from core.ingestion import execute_ingest_plan

        plan_id = self.app.app_state.get('ingest_plan_id')
        if not plan_id:
            raise RuntimeError('Plano de ingestao nao encontrado.')

        def cb(current, total, src):
            if self._stop_event.is_set():
                return

            processed = current + 1
            self._processed = processed
            try:
                size = src.stat().st_size
            except OSError:
                size = 0
            with self._bytes_lock:
                self._copied_bytes += size
                copied = self._copied_bytes

            elapsed = time.time() - self._start_time
            speed = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            progress = processed / total if total > 0 else 0
            now = time.monotonic()
            is_last = processed >= total
            if not is_last and now - self._last_ui_update < 0.10:
                return
            self._last_ui_update = now

            self.parent.after(
                0,
                lambda p=progress, c=processed, t=total, s=src, sp=speed, r=remaining, f=copied:
                    self._update_ui(p, c, t, s, sp, r, f)
            )

        stats = execute_ingest_plan(plan_id, callback=cb)
        self.app.app_state['exec_result'] = stats
        self.parent.after(0, self._on_done)

    def _update_ui(self, progress, current, total, src, speed, remaining, copied=0):
        self.progress_var.set(progress)
        self.progress_label.configure(text=f'{format_count(current)} / {format_count(total)}')
        self.file_label.configure(text=f'Processando: {src.name}')
        self.speed_label.configure(text=f'Velocidade: {format_speed(speed)}')
        self.eta_label.configure(text=format_eta(remaining, speed))
        self.copied_label.configure(text=f'Copiado: {format_size(copied)}')

        status_icon = '✓' if speed > 0 else '⟳'
        self._log(f'{status_icon} {src.name}')

    def _on_worker_error(self, msg: str):
        self._running = False
        self._log(f'\n✕ Erro fatal: {msg}')
        self._log('Verifique ~/.photovault/error.log para detalhes.')
        self.start_btn.configure(state='normal', text='▶  Iniciar')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        try:
            self.workers_btn.configure(state='normal')
            self._settings_frame.configure(fg_color=COLOR_CARD)
        except Exception:
            pass

    def _save_session(self, status: str = 'completed') -> None:
        from datetime import datetime
        from core.database import save_session
        result = self.app.app_state.get('exec_result')
        dup = self.app.app_state.get('dup_result')
        if isinstance(result, dict):
            processed = result.get('processed', 0)
            errors = result.get('errors', 0)
            total = result.get('total', self._total)
        else:
            processed = result.processed if result else self._processed
            errors = result.errors if result else 0
            total = result.total if result else self._total
        try:
            save_session({
                'started_at': datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else None,
                'completed_at': datetime.now().isoformat(),
                'sources': [s['path'] for s in self.app.app_state.get('sources', [])],
                'destination': str(self.app.app_state.get('destination', '')),
                'files_processed': processed,
                'files_moved': processed,
                'duplicates_found': len(dup.exact) + len(dup.visual) if dup else 0,
                'space_freed': dup.space_wasted if dup else 0,
                'errors': errors,
                'total_files': total,
                'status': status,
            })
        except Exception:
            pass

    def _on_done(self):
        self._running = False
        result = self.app.app_state.get('exec_result')
        if isinstance(result, dict):
            elapsed = time.time() - self._start_time
            self._log(f'\n=== Concluido em {elapsed:.1f}s ===')
            self._log(f'Processados: {result.get("processed", 0)}')
            self._log(f'Erros: {result.get("errors", 0)}')
            self._log(f'Ignorados: {result.get("skipped", 0)}')
            self.start_btn.configure(state='normal', text='Concluido')
            self.pause_btn.configure(state='disabled')
            self.cancel_btn.configure(state='disabled')
            try:
                self.workers_btn.configure(state='normal')
                self._settings_frame.configure(fg_color=COLOR_CARD)
            except Exception:
                pass
            self.progress_var.set(1.0)
            self._save_session('completed')
            self.main_window.navigate('report')
            return
        if result:
            elapsed = time.time() - self._start_time
            self._log(f'\n=== Concluído em {elapsed:.1f}s ===')
            self._log(f'Processados: {result.processed}')
            self._log(f'Erros: {result.errors}')
            self._log(f'Ignorados: {result.skipped}')

        self.start_btn.configure(state='normal', text='✓ Concluído')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        try:
            self.workers_btn.configure(state='normal')
            self._settings_frame.configure(fg_color=COLOR_CARD)
        except Exception:
            pass
        self.progress_var.set(1.0)

        self._save_session('completed')

        plan = self.app.app_state.get('plan')
        if plan:
            import threading
            threading.Thread(
                target=_record_to_index,
                args=(plan.operations, plan.destination),
                daemon=True
            ).start()

        self.main_window.navigate('report')

    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()  # pausa todos os workers
            self.pause_btn.configure(text='▶  Retomar')
            self._log('⏸ Pausado.')
        else:
            self._pause_event.set()  # retoma todos os workers
            self.pause_btn.configure(text='⏸  Pausar')
            self._log('▶ Retomando...')

    def _cancel(self):
        self._running = False
        self._stop_event.set()
        self._pause_event.set()  # desbloqueia workers pausados para que possam ver stop
        self._log('✕ Cancelado pelo usuário.')
        self.start_btn.configure(state='normal', text='▶  Iniciar')
        self.pause_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        try:
            self.workers_btn.configure(state='normal')
            self._settings_frame.configure(fg_color=COLOR_CARD)
        except Exception:
            pass
        if self._start_time:
            self._save_session('cancelled')

    def refresh(self):
        # Reset for new run
        if not self._running:
            self.start_btn.configure(state='normal', text='▶  Iniciar')
            self.progress_var.set(0)
            self.progress_label.configure(text='0 / 0')
            self.file_label.configure(text='Pronto para executar.')
