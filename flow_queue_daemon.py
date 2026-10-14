import asyncio
import importlib
import json
import os
import re
import sqlite3
import sys
import uuid
from collections import deque
from datetime import datetime
from aiohttp import web
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import flowapi

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = int(os.environ.get("FLOW_DAEMON_PORT", "9334"))
DB_PATH = os.path.join(flowapi.CHROME_PROFILE_DIR, "flow_queue.db")


def init_db():
    os.makedirs(flowapi.CHROME_PROFILE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            workspace TEXT,
            tipo TEXT,
            prompt TEXT,
            modelo TEXT,
            proporcao TEXT,
            duracao TEXT,
            resolucao TEXT,
            quantidade TEXT,
            imagem_in TEXT,
            imagem_out TEXT,
            swap_frames INTEGER,
            ingredientes TEXT,
            output_path TEXT,
            status TEXT,
            media_id TEXT,
            file_path TEXT,
            error TEXT,
            created_at TEXT,
            updated_at TEXT,
            priority INTEGER DEFAULT 100
        )
    """)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 100")
    except Exception:
        pass
    conn.commit()
    conn.close()


def db_save_job(job: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO jobs (
            job_id, workspace, tipo, prompt, modelo, proporcao, duracao, resolucao,
            quantidade, imagem_in, imagem_out, swap_frames, ingredientes,
            output_path, status, media_id, file_path, error, created_at, updated_at, priority
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job["job_id"],
        job.get("workspace", ""),
        job.get("tipo", "video"),
        job.get("prompt", ""),
        job.get("modelo", ""),
        job.get("proporcao", "16:9"),
        job.get("duracao", "8s"),
        job.get("resolucao", "720p"),
        job.get("quantidade", "x1"),
        job.get("imagem_in") or "",
        job.get("imagem_out") or "",
        1 if job.get("swap_frames") else 0,
        json.dumps(job.get("ingredientes") or [], ensure_ascii=False),
        job.get("output_path", ""),
        job.get("status", "queued"),
        job.get("media_id") or "",
        job.get("file_path") or "",
        job.get("error") or "",
        job.get("created_at", ""),
        datetime.now().isoformat(timespec="seconds"),
        job.get("priority", 100),
    ))
    conn.commit()
    conn.close()


def db_list_recent_jobs(limit=50):
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["ingredientes"] = json.loads(r.get("ingredientes") or "[]")
        except Exception:
            r["ingredientes"] = []
        r["swap_frames"] = bool(r.get("swap_frames"))
    return rows


class FlowCentralDaemon:
    """
    Daemon centralizado de fila unica com Telemetria de Auto-Healing.
    Gerencia uma unica instancia isolada do Google Chrome (porta 9333)
    e processa requisicoes de multiplos projetos/workspaces em serie sem conflito.
    """

    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self._counter = 0
        self.jobs = {}
        self.job_events = {}
        self.browser_lock = asyncio.Lock()
        self.playwright = None
        self.browser = None
        self.page = None
        self.invisivel = True
        self.active_job_id = None
        self.last_config_signature = None
        self.config_padrao = flowapi.carregar_config()
        self.recent_rpcs = deque(maxlen=40)
        self._attached_pages = set()

        for r in reversed(db_list_recent_jobs(100)):
            if r["status"] in ("queued", "running", "rendering", "downloading"):
                r["status"] = "interrupted"
                db_save_job(r)
            self.jobs[r["job_id"]] = r

    async def start(self):
        self.playwright = await async_playwright().start()
        asyncio.create_task(self.worker_loop())

    async def stop(self):
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    def _attach_network_sniffer(self, page):
        """Monitora chamadas batchexecute para facilitar Auto-Healing caso o Google mude RPC IDs."""
        if id(page) in self._attached_pages:
            return
        self._attached_pages.add(id(page))

        async def on_response(resp):
            try:
                if "batchexecute" in resp.url:
                    m = re.search(r"rpcids=([^&]+)", resp.url)
                    rpcid = m.group(1) if m else "unknown"
                    txt = ""
                    try:
                        txt = (await resp.text())[:500]
                    except Exception:
                        pass
                    self.recent_rpcs.append({
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "rpcids": rpcid,
                        "status": resp.status,
                        "url": resp.url[:180],
                        "preview": txt,
                    })
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

    async def ensure_browser_and_page(self, force_visible=None, ensure_project=True):
        primeiro_uso = not flowapi.ja_fez_login_inicial()
        if force_visible is not None:
            self.invisivel = not force_visible
        elif primeiro_uso:
            self.invisivel = False

        precisa_reconectar = False
        if not self.browser or not self.browser.is_connected():
            precisa_reconectar = True
        elif self.page and self.page.is_closed():
            precisa_reconectar = True

        if precisa_reconectar:
            self.browser = None
            self.page = None
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{flowapi.CHROME_PORT}"
                )
            except Exception:
                flowapi.iniciar_chrome_flow(
                    invisivel=self.invisivel,
                    porta=flowapi.CHROME_PORT,
                    profile_dir=flowapi.CHROME_PROFILE_DIR,
                )
                for _ in range(20):
                    await asyncio.sleep(1)
                    try:
                        self.browser = await self.playwright.chromium.connect_over_cdp(
                            f"http://127.0.0.1:{flowapi.CHROME_PORT}"
                        )
                        break
                    except Exception:
                        pass
                if not self.browser:
                    raise RuntimeError(
                        f"Nao foi possivel iniciar ou conectar ao Chrome na porta {flowapi.CHROME_PORT}"
                    )

        ctx = self.browser.contexts[0]
        if not self.page or self.page.is_closed():
            for pg in ctx.pages:
                if "flow.google" in pg.url.lower():
                    self.page = pg
                    break
            if not self.page:
                for pg in ctx.pages:
                    if "google" in pg.url.lower():
                        self.page = pg
                        break
            if not self.page:
                self.page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        self._attach_network_sniffer(self.page)
        await flowapi.posicionar_janela_chrome(self.page, invisivel=self.invisivel)

        if "flow.google.com" not in self.page.url.lower():
            await self.page.goto("https://flow.google.com/", wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

        params = await flowapi.obter_parametros_pagina(self.page)
        logado = bool(params.get("atToken"))

        if logado and not flowapi.ja_fez_login_inicial():
            flowapi.marcar_login_concluido()

        if ensure_project and logado:
            if "project" not in self.page.url.lower():
                await flowapi.criar_projeto(self.page)
                self.last_config_signature = None
                params = await flowapi.obter_parametros_pagina(self.page)

        return self.page, params, logado

    def resolver_caminho_saida(self, job: dict) -> str:
        tipo = job.get("tipo", "video")
        ext_padrao = ".png" if tipo == "imagem" else ".mp4"
        out_raw = (job.get("output_path") or "").strip().strip('"').strip("'")

        if not out_raw:
            pasta_padrao = os.path.join(
                BASE_DIR, "imagens_geradas" if tipo == "imagem" else "videos_gerados"
            )
            os.makedirs(pasta_padrao, exist_ok=True)
            nome_seguro = re.sub(r"[^A-Za-z0-9]", "_", job.get("prompt", "flow"))[:40]
            return os.path.join(pasta_padrao, f"{nome_seguro}_{job['job_id'][:8]}{ext_padrao}")

        out_abs = os.path.abspath(out_raw)
        _, ext = os.path.splitext(out_abs)
        if ext.lower() in (".mp4", ".png", ".jpg", ".jpeg", ".webp", ".mov"):
            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
            return out_abs
        else:
            os.makedirs(out_abs, exist_ok=True)
            nome_seguro = re.sub(r"[^A-Za-z0-9]", "_", job.get("prompt", "flow"))[:40]
            return os.path.join(out_abs, f"{nome_seguro}_{job['job_id'][:8]}{ext_padrao}")

    async def process_single_job(self, job: dict):
        job_id = job["job_id"]
        self.active_job_id = job_id
        job["status"] = "running"
        db_save_job(job)

        try:
            async with self.browser_lock:
                page, params, logado = await self.ensure_browser_and_page(ensure_project=True)
                if not logado:
                    await flowapi.posicionar_janela_chrome(page, invisivel=False)
                    self.invisivel = False
                    raise RuntimeError(
                        "Usuario nao esta logado no Google Flow. O navegador foi aberto na tela para login."
                    )

                tipo = job.get("tipo", "video").lower().strip()
                tipo = "imagem" if tipo in ("image", "img", "imagem") else "video"
                job["tipo"] = tipo

                assinatura = (
                    tipo,
                    bool(job.get("imagem_in") or job.get("imagem_out")),
                    bool(job.get("ingredientes")),
                    job.get("modelo"),
                    job.get("proporcao"),
                    job.get("duracao"),
                    job.get("resolucao"),
                    job.get("quantidade"),
                )
                if assinatura != self.last_config_signature:
                    await flowapi.configurar_geracao(page, job, self.config_padrao)
                    self.last_config_signature = assinatura

                params = await flowapi.obter_parametros_pagina(page)
                if tipo == "imagem":
                    media_id = await flowapi.gerar_imagem(page, job, params)
                else:
                    media_id = await flowapi.gerar_video(page, job, params)

                if not media_id:
                    raise RuntimeError(
                        "Falha ao disparar geracao no Google Flow (media_id vazio). "
                        "Possivel mudanca de seletor UI, RPC ID ou bloqueio temporario."
                    )

                job["media_id"] = media_id
                job["status"] = "rendering"
                db_save_job(job)

                pronto = False
                max_tentativas = 40 if tipo == "imagem" else 95
                for tentativa in range(max_tentativas):
                    if tipo == "video" or tentativa > 0:
                        await asyncio.sleep(4 if tipo == "video" else 1.5)
                    pronto, _ = await flowapi.checar_status(page, media_id, params, tipo)
                    if pronto:
                        break

                caminho_final = self.resolver_caminho_saida(job)
                job["status"] = "downloading"
                db_save_job(job)

                if tipo == "imagem":
                    sucesso = await flowapi.baixar_imagem(page, media_id, caminho_final, params)
                else:
                    sucesso = await flowapi.baixar_video(page, media_id, caminho_final, params)

                if not sucesso or not os.path.exists(caminho_final):
                    raise RuntimeError(
                        f"Midia gerada (ID: {media_id}), mas houve falha ao baixar para {caminho_final}."
                    )

                job["file_path"] = caminho_final
                job["status"] = "completed"
                job["error"] = ""
                db_save_job(job)

        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            # Coleta telemetria automatica para Auto-Healing pelo Agente de IA
            try:
                if self.page and not self.page.is_closed():
                    diag = await flowapi.coletar_diagnostico_pagina(
                        self.page,
                        motivo=f"Job {job_id} failed: {e}",
                        recent_rpcs=list(self.recent_rpcs),
                        take_screenshot=True,
                    )
                    job["diagnostics"] = {
                        "report_path": diag.get("report_path"),
                        "screenshot_path": diag.get("screenshot_path"),
                        "page_url": diag.get("page_url"),
                        "alerts_or_toasts": diag.get("dom_snapshot", {}).get("alerts_or_toasts", []),
                        "recent_rpcs": list(self.recent_rpcs)[-5:],
                        "auto_healing_hint": diag.get("auto_healing_instructions"),
                    }
            except Exception:
                pass
            db_save_job(job)
        finally:
            self.active_job_id = None
            ev = self.job_events.get(job_id)
            if ev:
                ev.set()

    async def worker_loop(self):
        while True:
            _, _, job_id = await self.queue.get()
            job = self.jobs.get(job_id)
            if job and job.get("status") == "queued":
                await self.process_single_job(job)
            self.queue.task_done()

    def _rebuild_queue(self):
        """Reconstroi a PriorityQueue com os jobs ainda pendentes na nova ordem de prioridade."""
        new_q = asyncio.PriorityQueue()
        queued_jobs = [j for j in self.jobs.values() if j.get("status") == "queued"]
        queued_jobs.sort(key=lambda x: (int(x.get("priority", 100)), x.get("created_at", "")))
        for j in queued_jobs:
            self._counter += 1
            new_q.put_nowait((int(j.get("priority", 100)), self._counter, j["job_id"]))
        self.queue = new_q

    def set_job_priority(self, job_id: str, new_priority: int) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.get("status") != "queued":
            return False
        job["priority"] = int(new_priority)
        db_save_job(job)
        self._rebuild_queue()
        return True

    def set_project_priority(self, workspace: str, new_priority: int) -> int:
        count = 0
        for job in self.jobs.values():
            if job.get("status") == "queued":
                job_ws = job.get("workspace") or ""
                if workspace.lower() in job_ws.lower() or os.path.basename(job_ws.rstrip("/\\")).lower() == workspace.lower():
                    job["priority"] = int(new_priority)
                    db_save_job(job)
                    count += 1
        if count > 0:
            self._rebuild_queue()
        return count

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        if job.get("status") in ("queued", "interrupted"):
            job["status"] = "cancelled"
            job["error"] = "Cancelado pelo usuario"
            db_save_job(job)
            ev = self.job_events.get(job_id)
            if ev:
                ev.set()
            self._rebuild_queue()
            return True
        return False

    def enqueue_job(self, payload: dict) -> dict:
        job_id = payload.get("job_id") or str(uuid.uuid4())
        tipo_raw = str(payload.get("tipo", "video")).lower().strip()
        tipo = "imagem" if tipo_raw in ("imagem", "image", "img") else "video"
        workspace = payload.get("workspace") or ""
        priority = int(payload.get("priority", 100))

        def resolve_input_path(p):
            if not p:
                return None
            p = str(p).strip().strip('"').strip("'")
            if os.path.isabs(p) and os.path.exists(p):
                return os.path.abspath(p)
            if workspace:
                cand = os.path.join(workspace, p)
                if os.path.exists(cand):
                    return os.path.abspath(cand)
            return flowapi.resolver_caminho_midia(p)

        img_in = resolve_input_path(payload.get("imagem_in") or payload.get("frame_in"))
        img_out = resolve_input_path(payload.get("imagem_out") or payload.get("frame_out"))
        ings_raw = payload.get("ingredientes") or []
        if isinstance(ings_raw, str):
            ings_raw = [x.strip() for x in ings_raw.split(",") if x.strip()]
        ings = [resolve_input_path(x) for x in ings_raw if x]

        out_path = payload.get("output_path") or ""
        if out_path and not os.path.isabs(out_path) and workspace:
            out_path = os.path.abspath(os.path.join(workspace, out_path))

        job = {
            "job_id": job_id,
            "workspace": workspace,
            "tipo": tipo,
            "prompt": str(payload.get("prompt", "")).strip(),
            "modelo": payload.get("modelo")
            or (
                self.config_padrao.get("modelo_imagem")
                if tipo == "imagem"
                else self.config_padrao.get("modelo_video")
            ),
            "proporcao": payload.get("proporcao") or self.config_padrao.get("proporcao", "16:9"),
            "duracao": payload.get("duracao") or self.config_padrao.get("duracao", "8s"),
            "resolucao": payload.get("resolucao") or self.config_padrao.get("resolucao", "720p"),
            "quantidade": payload.get("quantidade") or self.config_padrao.get("quantidade", "x1"),
            "imagem_in": img_in,
            "imagem_out": img_out,
            "swap_frames": bool(payload.get("swap_frames", False)),
            "ingredientes": ings,
            "output_path": out_path,
            "status": "queued",
            "media_id": None,
            "file_path": None,
            "error": None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "priority": priority,
        }

        self.jobs[job_id] = job
        self.job_events[job_id] = asyncio.Event()
        db_save_job(job)
        self._counter += 1
        self.queue.put_nowait((priority, self._counter, job_id))
        return job
        return job


daemon = FlowCentralDaemon()


async def handle_health(request: web.Request):
    browser_connected = bool(daemon.browser and daemon.browser.is_connected())
    return web.json_response({
        "ok": True,
        "daemon_port": DAEMON_PORT,
        "chrome_port": flowapi.CHROME_PORT,
        "profile_dir": flowapi.CHROME_PROFILE_DIR,
        "login_completed_marker": flowapi.ja_fez_login_inicial(),
        "browser_connected": browser_connected,
        "browser_hidden": daemon.invisivel,
        "queue_size": daemon.queue.qsize(),
        "active_job_id": daemon.active_job_id,
        "codebase_dir": BASE_DIR,
    })


async def handle_enqueue(request: web.Request):
    data = await request.json()
    wait = bool(data.get("wait", True))
    timeout = float(data.get("timeout", 600))

    items = data.get("items")
    if isinstance(items, list):
        created_jobs = [daemon.enqueue_job(it) for it in items]
        if wait:
            events = [daemon.job_events[j["job_id"]].wait() for j in created_jobs]
            await asyncio.wait_for(asyncio.gather(*events), timeout=timeout)
            created_jobs = [daemon.jobs[j["job_id"]] for j in created_jobs]
        return web.json_response({"ok": True, "jobs": created_jobs})

    job = daemon.enqueue_job(data)
    job_id = job["job_id"]
    if wait:
        ev = daemon.job_events.get(job_id)
        if ev:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        job = daemon.jobs[job_id]

    return web.json_response({
        "ok": job.get("status") != "failed",
        "job": job,
    })


async def handle_job_status(request: web.Request):
    job_id = request.match_info["job_id"]
    wait = request.query.get("wait", "0") in ("1", "true", "True")
    job = daemon.jobs.get(job_id)
    if not job:
        return web.json_response({"ok": False, "error": f"Job {job_id} nao encontrado"}, status=404)

    if wait and job["status"] in ("queued", "running", "rendering", "downloading"):
        ev = daemon.job_events.get(job_id)
        if ev:
            await asyncio.wait_for(ev.wait(), timeout=600)
        job = daemon.jobs.get(job_id)

    return web.json_response({"ok": True, "job": job})


async def handle_queue_summary(request: web.Request):
    all_jobs = list(daemon.jobs.values())
    all_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    queued = [j for j in all_jobs if j["status"] == "queued"]
    queued.sort(key=lambda x: (int(x.get("priority", 100)), x.get("created_at", "")))
    running = [j for j in all_jobs if j["status"] in ("running", "rendering", "downloading")]
    completed = [j for j in all_jobs if j["status"] == "completed"][:30]
    failed = [j for j in all_jobs if j["status"] in ("failed", "cancelled", "interrupted")][:15]

    projects = {}
    for j in queued:
        ws = j.get("workspace") or "Geral"
        nome_curto = os.path.basename(ws.rstrip("\\/")) if ws != "Geral" else "Geral"
        if nome_curto not in projects:
            projects[nome_curto] = {
                "workspace": ws,
                "name": nome_curto,
                "count": 0,
                "highest_priority": 999,
            }
        projects[nome_curto]["count"] += 1
        p_val = int(j.get("priority", 100))
        if p_val < projects[nome_curto]["highest_priority"]:
            projects[nome_curto]["highest_priority"] = p_val

    return web.json_response({
        "ok": True,
        "active_job_id": daemon.active_job_id,
        "queue_pending_count": daemon.queue.qsize(),
        "running": running,
        "queued": queued,
        "recent_completed": completed,
        "recent_failed": failed,
        "projects": list(projects.values()),
    })


async def handle_job_priority(request: web.Request):
    job_id = request.match_info["job_id"]
    data = await request.json()
    new_priority = int(data.get("priority", 10))
    ok = daemon.set_job_priority(job_id, new_priority)
    return web.json_response({"ok": ok, "job": daemon.jobs.get(job_id)})


async def handle_project_priority(request: web.Request):
    data = await request.json()
    workspace = data.get("workspace", "")
    new_priority = int(data.get("priority", 10))
    count = daemon.set_project_priority(workspace, new_priority)
    return web.json_response({"ok": count > 0, "updated_count": count})


async def handle_cancel_job(request: web.Request):
    job_id = request.match_info["job_id"]
    ok = daemon.cancel_job(job_id)
    return web.json_response({"ok": ok, "job_id": job_id})


async def monitor_login_and_close():
    logou_nesta_sessao = False
    for _ in range(600):
        await asyncio.sleep(2)
        try:
            if not daemon.browser or not daemon.browser.is_connected():
                if logou_nesta_sessao:
                    flowapi.marcar_login_concluido()
                    daemon.invisivel = True
                break
            if daemon.page and not daemon.page.is_closed():
                if "flow.google.com" in daemon.page.url.lower():
                    params = await flowapi.obter_parametros_pagina(daemon.page)
                    if params.get("atToken"):
                        logou_nesta_sessao = True
                        flowapi.marcar_login_concluido()
        except Exception:
            if logou_nesta_sessao:
                flowapi.marcar_login_concluido()
                daemon.invisivel = True
            break


async def handle_browser_visibility(request: web.Request):
    action = request.match_info["action"].lower()
    async with daemon.browser_lock:
        if action in ("show", "login"):
            page, params, logado = await daemon.ensure_browser_and_page(
                force_visible=True,
                ensure_project=(action == "show" and flowapi.ja_fez_login_inicial()),
            )
            await flowapi.posicionar_janela_chrome(page, invisivel=False)
            daemon.invisivel = False
            if action == "login":
                asyncio.create_task(monitor_login_and_close())
            return web.json_response({
                "ok": True,
                "action": action,
                "visible": True,
                "logged_in": logado,
                "login_completed_marker": flowapi.ja_fez_login_inicial(),
                "url": page.url,
                "message": (
                    "Navegador Google Chrome (perfil isolado Flow) visivel na tela! "
                    + (
                        "Voce ja esta logado no Flow."
                        if logado
                        else "Faca login na sua conta Google/Flow. Quando terminar, pode fechar o navegador ou usar hide_browser."
                    )
                ),
            })
        elif action == "hide":
            page, params, logado = await daemon.ensure_browser_and_page(
                force_visible=False, ensure_project=False
            )
            await flowapi.posicionar_janela_chrome(page, invisivel=True)
            daemon.invisivel = True
            if logado:
                flowapi.marcar_login_concluido()
            return web.json_response({
                "ok": True,
                "action": "hide",
                "visible": False,
                "logged_in": logado,
                "url": page.url,
                "message": "Navegador movido para fora da tela (X=-2400, Y=0) em modo invisivel.",
            })
        elif action == "new_project":
            page, params, logado = await daemon.ensure_browser_and_page(ensure_project=False)
            if not logado:
                return web.json_response({"ok": False, "error": "Nao logado no Flow"}, status=400)
            ok = await flowapi.criar_projeto(page)
            daemon.last_config_signature = None
            return web.json_response({"ok": ok, "url": page.url})
        else:
            return web.json_response({"ok": False, "error": f"Acao desconhecida: {action}"}, status=400)


async def handle_diagnose(request: web.Request):
    """Endpoint de Auto-Healing: inspeciona DOM ao vivo, RPCs de rede recentes e tira screenshot."""
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    open_settings = bool(data.get("open_settings_menu", False))
    take_screenshot = bool(data.get("take_screenshot", True))

    async with daemon.browser_lock:
        page, params, logado = await daemon.ensure_browser_and_page(ensure_project=False)
        if open_settings:
            try:
                sels = flowapi.carregar_seletores()["selectors"]
                btn = page.locator(sels["settings_trigger"]).first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(0.8)
            except Exception:
                pass
        diag = await flowapi.coletar_diagnostico_pagina(
            page,
            motivo=data.get("reason", "Manual AI Agent Diagnostic Call"),
            recent_rpcs=list(daemon.recent_rpcs),
            take_screenshot=take_screenshot,
        )
        if open_settings:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
        return web.json_response({"ok": True, "diagnostics": diag})


async def handle_selectors(request: web.Request):
    """Permite que o Agente de IA atualize selectors.json em tempo real (Auto-Healing)."""
    if request.method == "GET":
        return web.json_response({"ok": True, "selectors": flowapi.carregar_seletores()})
    data = await request.json()
    atualizado = flowapi.atualizar_seletores(data)
    daemon.last_config_signature = None
    return web.json_response({"ok": True, "selectors": atualizado})


async def handle_reload(request: web.Request):
    """Recarrega o modulo flowapi.py em memoria sem derrubar a fila caso o agente tenha editado o codigo."""
    importlib.reload(flowapi)
    daemon.config_padrao = flowapi.carregar_config()
    daemon.last_config_signature = None
    return web.json_response({
        "ok": True,
        "message": "Modulo flowapi.py e selectors.json recarregados com sucesso em tempo real!",
    })


async def on_startup(app: web.Application):
    init_db()
    await daemon.start()


async def on_cleanup(app: web.Application):
    await daemon.stop()


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_route("OPTIONS", "/{tail:.*}", lambda r: web.Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "*", "Access-Control-Allow-Headers": "*"}))
    app.router.add_get("/health", handle_health)
    app.router.add_post("/enqueue", handle_enqueue)
    app.router.add_get("/queue", handle_queue_summary)
    app.router.add_get("/jobs/{job_id}", handle_job_status)
    app.router.add_post("/jobs/{job_id}/priority", handle_job_priority)
    app.router.add_post("/jobs/{job_id}/cancel", handle_cancel_job)
    app.router.add_post("/projects/priority", handle_project_priority)
    app.router.add_post("/browser/{action}", handle_browser_visibility)
    app.router.add_post("/diagnose", handle_diagnose)
    app.router.add_get("/selectors", handle_selectors)
    app.router.add_post("/selectors", handle_selectors)
    app.router.add_post("/reload", handle_reload)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host=DAEMON_HOST, port=DAEMON_PORT, print=None)

