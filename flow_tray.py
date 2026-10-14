#!/usr/bin/env python3
"""
Flow Studio — System Tray & Apple Control Center Flyout Popup
- Zero icone de Python na barra de tarefas (WS_EX_TOOLWINDOW + ITaskbarList::DeleteTab)
- Cantos arredondados nativos via Windows DWM (DWMWA_WINDOW_CORNER_PREFERENCE)
- 100% livre de travamentos (comunicacao assincrona via CORS + controle Win32 thread-safe)
- Toggle inteligente no clique do Tray (abre se fechado, recolhe se aberto)
"""

import ctypes
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
import webview

BASE_DIR = Path(__file__).resolve().parent
DAEMON_SCRIPT = BASE_DIR / "flow_queue_daemon.py"
DAEMON_URL = "http://127.0.0.1:9334"

POPUP_WIDTH = 430
POPUP_HEIGHT = 600


def ensure_daemon():
    """Garante que o Daemon Central esteja rodando na porta 9334."""
    try:
        req = urllib.request.Request(f"{DAEMON_URL}/health")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = sys.executable

    if os.name == "nt":
        cmd_str = f'"{pythonw_exe}" "{DAEMON_SCRIPT}"'
        ps_cmd = (
            f"Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
            f"-Arguments @{{CommandLine='{cmd_str}'; CurrentDirectory='{BASE_DIR}'}} | Out-Null"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            [sys.executable, str(DAEMON_SCRIPT)],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    for _ in range(25):
        time.sleep(0.4)
        try:
            with urllib.request.urlopen(f"{DAEMON_URL}/health", timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
    return False


def get_flyout_position(width=POPUP_WIDTH, height=POPUP_HEIGHT, margin=12):
    """Calcula X e Y para o popup flutuar no canto inferior direito logo acima da barra de tarefas."""
    if os.name == "nt":
        try:
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
            pos_x = rect.right - width - margin
            pos_y = rect.bottom - height - margin
            return max(10, pos_x), max(10, pos_y)
        except Exception:
            pass
    return 100, 100


def create_tray_icon_image(status="ready"):
    """
    Desenha um icone grande e super nitido para a bandeja do sistema (64x64):
      - ready: Verde Esmeralda Vibrante
      - rendering: Ambar Dourado Brilhante
      - offline / login: Vermelho Coral
    """
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if status == "rendering":
        primary = (245, 158, 11, 255)
        glow = (245, 158, 11, 85)
        ring = (253, 224, 71, 255)
    elif status in ("offline", "login"):
        primary = (239, 68, 68, 255)
        glow = (239, 68, 68, 85)
        ring = (252, 165, 165, 255)
    else:
        primary = (16, 185, 129, 255)
        glow = (16, 185, 129, 85)
        ring = (110, 231, 183, 255)

    draw.ellipse((2, 2, 62, 62), fill=glow)
    draw.ellipse((6, 6, 58, 58), fill=primary, outline=ring, width=3)
    draw.polygon([(25, 19), (25, 45), (47, 32)], fill=(255, 255, 255, 255))
    return img


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Flow Studio Flyout</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-base: #0b0f19;
      --bg-card: rgba(255, 255, 255, 0.045);
      --bg-card-hover: rgba(255, 255, 255, 0.07);
      --bg-input: rgba(0, 0, 0, 0.35);
      --border-subtle: rgba(255, 255, 255, 0.09);
      --border-highlight: rgba(255, 255, 255, 0.18);
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.35);
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-dim: #64748b;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
      -webkit-font-smoothing: antialiased;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", sans-serif;
      background:
        radial-gradient(120% 80% at 15% 0%, rgba(99, 102, 241, 0.18) 0%, transparent 55%),
        radial-gradient(100% 70% at 90% 100%, rgba(16, 185, 129, 0.12) 0%, transparent 50%),
        linear-gradient(180deg, #111726 0%, #0a0e17 100%);
      color: var(--text-primary);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 16px;
    }

    .flyout-wrapper {
      display: flex;
      flex-direction: column;
      height: 100%;
      animation: popIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }

    @keyframes popIn {
      from { opacity: 0; transform: translateY(10px) scale(0.985); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    /* TOP HEADER */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px 10px;
      -webkit-app-region: drag;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-icon {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    .brand-icon svg {
      width: 15px;
      height: 15px;
      fill: #fff;
    }
    .brand-text {
      display: flex;
      flex-direction: column;
    }
    .brand-title {
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.3px;
      color: #fff;
    }
    .brand-sub {
      font-size: 10px;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--emerald);
      box-shadow: 0 0 6px var(--emerald);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 6px;
      -webkit-app-region: no-drag;
    }
    .icon-btn {
      width: 26px;
      height: 26px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.15s;
    }
    .icon-btn:hover {
      background: rgba(255, 255, 255, 0.12);
      color: #fff;
    }

    /* SEGMENTED ICON NAVIGATION BAR (APPLE CONTROL CENTER STYLE) */
    .nav-container {
      padding: 0 16px 10px;
    }
    .nav-pills {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 3px;
      gap: 3px;
    }
    .nav-pill {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 7px 4px;
      border-radius: 9px;
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.18s ease;
      position: relative;
    }
    .nav-pill svg {
      width: 15px;
      height: 15px;
      stroke-width: 2.1;
    }
    .nav-pill:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.04);
    }
    .nav-pill.active {
      background: rgba(255, 255, 255, 0.11);
      color: #fff;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    }
    .nav-pill.active svg {
      stroke: #818cf8;
    }
    .badge-counter {
      background: var(--accent);
      color: #fff;
      font-size: 9px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 999px;
      min-width: 16px;
      text-align: center;
    }

    /* CONTENT AREA */
    .main-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 4px 16px 16px;
    }
    .main-scroll::-webkit-scrollbar { width: 4px; }
    .main-scroll::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.12);
      border-radius: 99px;
    }
    .tab-view { display: none; }
    .tab-view.active {
      display: block;
      animation: tabFade 0.16s ease-out;
    }
    @keyframes tabFade {
      from { opacity: 0; transform: translateY(3px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* CARDS */
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 13px;
      padding: 12px;
      margin-bottom: 10px;
      backdrop-filter: blur(16px);
    }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 10.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-secondary);
    }

    /* ACTIVE RENDERING CARD */
    .card-active-job {
      background: linear-gradient(135deg, rgba(245, 158, 11, 0.14) 0%, rgba(99, 102, 241, 0.10) 100%);
      border-color: rgba(245, 158, 11, 0.4);
    }
    .progress-bar-indeterminate {
      height: 3px;
      width: 100%;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 99px;
      overflow: hidden;
      margin-top: 8px;
    }
    .progress-bar-indeterminate::after {
      content: '';
      display: block;
      height: 100%;
      width: 40%;
      background: linear-gradient(90deg, #f59e0b, #818cf8);
      border-radius: 99px;
      animation: progressSlide 1.4s infinite ease-in-out;
    }
    @keyframes progressSlide {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(260%); }
    }

    /* QUEUE ITEMS */
    .q-item {
      background: rgba(0, 0, 0, 0.28);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 9px 11px;
      margin-bottom: 7px;
      transition: border-color 0.15s;
    }
    .q-item:hover { border-color: var(--border-highlight); }
    .q-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 5px;
    }
    .tags { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
    .tag {
      font-size: 9.5px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 5px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }
    .tag-vid { background: rgba(99, 102, 241, 0.22); color: #c7d2fe; border: 1px solid rgba(99, 102, 241, 0.35); }
    .tag-img { background: rgba(16, 185, 129, 0.22); color: #a7f3d0; border: 1px solid rgba(16, 185, 129, 0.35); }
    .tag-proj { background: rgba(244, 63, 94, 0.18); color: #fecdd3; border: 1px solid rgba(244, 63, 94, 0.3); }
    .tag-prio { background: rgba(245, 158, 11, 0.22); color: #fde68a; border: 1px solid rgba(245, 158, 11, 0.4); }
    .q-prompt {
      font-size: 11.5px;
      color: #e2e8f0;
      line-height: 1.35;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .q-actions {
      display: flex;
      justify-content: flex-end;
      gap: 5px;
      margin-top: 6px;
    }

    /* BUTTONS */
    .btn {
      padding: 6px 11px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      border: 1px solid transparent;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      transition: all 0.15s;
      color: #fff;
    }
    .btn-xs { padding: 3px 8px; font-size: 10px; border-radius: 6px; }
    .btn-primary {
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }
    .btn-primary:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .btn-glass {
      background: rgba(255, 255, 255, 0.07);
      border-color: var(--border-subtle);
      color: #e2e8f0;
    }
    .btn-glass:hover { background: rgba(255, 255, 255, 0.13); }
    .btn-amber {
      background: rgba(245, 158, 11, 0.18);
      border-color: rgba(245, 158, 11, 0.38);
      color: #fde68a;
    }
    .btn-amber:hover { background: rgba(245, 158, 11, 0.28); }
    .btn-rose {
      background: rgba(244, 63, 94, 0.18);
      border-color: rgba(244, 63, 94, 0.38);
      color: #fecdd3;
    }
    .btn-rose:hover { background: rgba(244, 63, 94, 0.28); }

    /* FORMS */
    .field { margin-bottom: 9px; }
    .label {
      display: block;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-secondary);
      margin-bottom: 4px;
    }
    input[type="text"], textarea, select {
      width: 100%;
      background: var(--bg-input);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 7px 10px;
      font-size: 11.5px;
      color: #fff;
      outline: none;
      font-family: inherit;
      transition: border-color 0.15s;
    }
    input[type="text"]:focus, textarea:focus, select:focus {
      border-color: #818cf8;
      box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
    }
    select option { background: #111726; color: #fff; }
    textarea { resize: none; height: 64px; line-height: 1.4; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }

    /* TYPE SWITCHER */
    .type-toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      background: var(--bg-input);
      border: 1px solid var(--border-subtle);
      border-radius: 9px;
      padding: 2px;
      gap: 2px;
    }
    .type-opt {
      text-align: center;
      padding: 6px 0;
      font-size: 11px;
      font-weight: 700;
      border-radius: 7px;
      cursor: pointer;
      color: var(--text-secondary);
      transition: all 0.15s;
    }
    .type-opt.active {
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      color: #fff;
    }

    /* CONTROL CENTER TILES (SISTEMA TAB) */
    .cc-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 10px;
    }
    .cc-tile {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 13px;
      padding: 12px;
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .cc-tile:hover {
      background: var(--bg-card-hover);
      border-color: var(--border-highlight);
      transform: translateY(-1px);
    }
    .cc-icon {
      width: 34px;
      height: 34px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      flex-shrink: 0;
    }
    .cc-info { display: flex; flex-direction: column; }
    .cc-title { font-size: 11.5px; font-weight: 700; color: #fff; }
    .cc-sub { font-size: 10px; color: var(--text-secondary); }

    .sys-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 7px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 11.5px;
    }
    .sys-row:last-child { border-bottom: none; }

    /* TOAST */
    #toast {
      position: fixed;
      bottom: 12px;
      left: 50%;
      transform: translateX(-50%) translateY(40px);
      background: rgba(15, 23, 42, 0.96);
      border: 1px solid rgba(129, 140, 248, 0.5);
      color: #fff;
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
      opacity: 0;
      pointer-events: none;
      transition: all 0.2s ease;
      z-index: 9999;
    }
    #toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }
  </style>
</head>
<body>
  <div class="flyout-wrapper">

    <!-- HEADER -->
    <div class="header">
      <div class="brand">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24"><polygon points="6 4 20 12 6 20 6 4"></polygon></svg>
        </div>
        <div class="brand-text">
          <span class="brand-title">Flow Studio</span>
          <span class="brand-sub">
            <span class="status-dot" id="topDot"></span>
            <span id="topStatusText">Fila Central Ativa</span>
          </span>
        </div>
      </div>
      <div class="header-actions">
        <div class="icon-btn" onclick="refreshAll()" title="Atualizar">↻</div>
        <div class="icon-btn" onclick="if(window.pywebview && window.pywebview.api) window.pywebview.api.close_flyout()" title="Recolher Painel">▾</div>
      </div>
    </div>

    <!-- TOP NAVIGATION PILLS (ICONS) -->
    <div class="nav-container">
      <div class="nav-pills">
        <div class="nav-pill active" id="nav-queue" onclick="switchTab('queue')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
          <span>Fila</span>
          <span class="badge-counter" id="badgeQueue">0</span>
        </div>
        <div class="nav-pill" id="nav-create" onclick="switchTab('create')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
          <span>Criar</span>
        </div>
        <div class="nav-pill" id="nav-batch" onclick="switchTab('batch')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
          <span>Lote</span>
        </div>
        <div class="nav-pill" id="nav-status" onclick="switchTab('status')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
          <span>Sistema</span>
        </div>
      </div>
    </div>

    <!-- SCROLLABLE CONTENT -->
    <div class="main-scroll">

      <!-- TAB 1: FILA CENTRAL (MCP + PAINEL) -->
      <div class="tab-view active" id="tab-queue">

        <!-- ACTIVE RENDERING -->
        <div class="card card-active-job" id="runningCard" style="display:none;">
          <div class="card-header">
            <span style="color:#fcd34d;">⚡ Gerando Agora no Google Flow</span>
            <span class="tag tag-proj" id="runningProj">Projeto</span>
          </div>
          <div id="runningBody" style="font-size:11.5px; color:#fff;"></div>
          <div class="progress-bar-indeterminate"></div>
        </div>

        <!-- PRIORIDADE POR PROJETO -->
        <div class="card" id="projectsCard" style="display:none;">
          <div class="card-header">
            <span>Projetos na Fila (Definir Prioridade)</span>
          </div>
          <div id="projectsList" style="display:flex; flex-direction:column; gap:6px;"></div>
        </div>

        <!-- QUEUED LIST -->
        <div class="card">
          <div class="card-header">
            <span>Fila de Espera (MCPs & Painel)</span>
            <span id="queuedCountText">0 na fila</span>
          </div>
          <div id="queuedList">
            <div style="text-align:center; padding:18px 8px; color:var(--text-dim); font-size:11.5px;">
              Nenhum vídeo ou imagem aguardando na fila.<br>
              <span style="font-size:10.5px;">Pedidos enviados por qualquer MCP aparecem aqui automaticamente!</span>
            </div>
          </div>
        </div>

        <!-- COMPLETED LIST -->
        <div class="card">
          <div class="card-header">
            <span>Concluídos Recentemente</span>
          </div>
          <div id="completedList"></div>
        </div>
      </div>

      <!-- TAB 2: CRIAR PROMPT INDIVIDUAL -->
      <div class="tab-view" id="tab-create">
        <div class="card">
          <div class="field">
            <label class="label">Formato</label>
            <div class="type-toggle">
              <div class="type-opt active" id="optVideo" onclick="setSingleType('video')">🎬 Vídeo</div>
              <div class="type-opt" id="optImage" onclick="setSingleType('imagem')">🖼️ Imagem</div>
            </div>
          </div>

          <div class="field">
            <label class="label">Prompt</label>
            <textarea id="singlePrompt" placeholder="Descreva a cena ou imagem que deseja gerar..."></textarea>
          </div>

          <div class="grid-2">
            <div class="field">
              <label class="label">Modelo</label>
              <select id="singleModel"></select>
            </div>
            <div class="field">
              <label class="label">Proporção</label>
              <select id="singleRatio">
                <option value="16:9">16:9 (Horizontal)</option>
                <option value="9:16">9:16 (Vertical)</option>
                <option value="1:1">1:1 (Quadrado)</option>
                <option value="4:3">4:3</option>
                <option value="3:4">3:4</option>
              </select>
            </div>
          </div>

          <div class="grid-3" id="singleVideoExtras">
            <div class="field">
              <label class="label">Duração</label>
              <select id="singleDur">
                <option value="8s">8s</option>
                <option value="4s">4s</option>
                <option value="6s">6s</option>
                <option value="10s">10s</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Resolução</label>
              <select id="singleRes">
                <option value="720p">720p</option>
                <option value="360p">360p</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Prioridade</label>
              <select id="singlePrio">
                <option value="100">Normal</option>
                <option value="10">⚡ Alta</option>
              </select>
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label class="label">Frame IN (Opcional)</label>
              <input type="text" id="singleIn" placeholder="Caminho img inicial...">
            </div>
            <div class="field">
              <label class="label">Frame OUT (Opcional)</label>
              <input type="text" id="singleOut" placeholder="Caminho img final...">
            </div>
          </div>

          <div class="field">
            <label class="label">Ingredientes (Caminhos separados por vírgula)</label>
            <input type="text" id="singleIng" placeholder="personagem.png, objeto.png...">
          </div>

          <div class="field">
            <label class="label">Salvar em (Pasta ou Arquivo)</label>
            <input type="text" id="singlePath" placeholder="Deixe vazio para pasta padrão...">
          </div>

          <button class="btn btn-primary" style="width:100%; padding:9px;" onclick="submitSingle()">
            🚀 Adicionar à Fila Central
          </button>
        </div>
      </div>

      <!-- TAB 3: LOTE TXT -->
      <div class="tab-view" id="tab-batch">
        <div class="card">
          <div class="card-header">
            <span>Subir Lista de Prompts (.TXT)</span>
            <span class="tag tag-prio" id="batchCounter">0 prompts</span>
          </div>

          <div class="field">
            <label class="btn btn-glass" style="width:100%; cursor:pointer; justify-content:center;">
              📂 Escolher Arquivo .TXT do Computador
              <input type="file" accept=".txt" style="display:none;" onchange="handleTxtUpload(event)">
            </label>
          </div>

          <div class="field">
            <label class="label">Ou cole os prompts abaixo (1 por linha)</label>
            <textarea id="batchText" style="height:105px;" placeholder="Prompt 1&#10;Prompt 2&#10;Prompt 3..." oninput="updateBatchCounter()"></textarea>
          </div>

          <div class="grid-2">
            <div class="field">
              <label class="label">Gerar todos como</label>
              <select id="batchType" onchange="syncBatchModels()">
                <option value="imagem">🖼️ Imagens</option>
                <option value="video">🎬 Vídeos</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Modelo do Lote</label>
              <select id="batchModel"></select>
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label class="label">Proporção do Lote</label>
              <select id="batchRatio">
                <option value="16:9">16:9 (Horizontal)</option>
                <option value="9:16">9:16 (Vertical)</option>
                <option value="1:1">1:1 (Quadrado)</option>
                <option value="4:3">4:3</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Prioridade na Fila</label>
              <select id="batchPrio">
                <option value="100">Normal</option>
                <option value="10">⚡ Alta Prioridade</option>
                <option value="200">Baixa (Background)</option>
              </select>
            </div>
          </div>

          <div class="field">
            <label class="label">Pasta de Destino para Todos</label>
            <input type="text" id="batchPath" placeholder="Ex: D:\MeuProjeto\Imagens">
          </div>

          <button class="btn btn-primary" style="width:100%; padding:9px;" onclick="submitBatch()">
            ⚡ Disparar Lote Inteiro na Fila
          </button>
        </div>
      </div>

      <!-- TAB 4: SISTEMA & NAVEGADOR (ESTILO CONTROL CENTER) -->
      <div class="tab-view" id="tab-status">
        <div class="cc-grid">
          <div class="cc-tile" onclick="runBrowserCmd('show')">
            <div class="cc-icon" style="background:rgba(99,102,241,0.2); color:#818cf8;">👁️</div>
            <div class="cc-info">
              <span class="cc-title">Mostrar Chrome</span>
              <span class="cc-sub">Trazer para a tela</span>
            </div>
          </div>
          <div class="cc-tile" onclick="runBrowserCmd('hide')">
            <div class="cc-icon" style="background:rgba(16,185,129,0.2); color:#10b981;">👻</div>
            <div class="cc-info">
              <span class="cc-title">Modo Invisível</span>
              <span class="cc-sub">Ocultar janela e ícone</span>
            </div>
          </div>
          <div class="cc-tile" onclick="runBrowserCmd('login')">
            <div class="cc-icon" style="background:rgba(245,158,11,0.2); color:#f59e0b;">🔑</div>
            <div class="cc-info">
              <span class="cc-title">Login Flow</span>
              <span class="cc-sub">Autenticar conta</span>
            </div>
          </div>
          <div class="cc-tile" onclick="runBrowserCmd('new_project')">
            <div class="cc-icon" style="background:rgba(244,63,94,0.2); color:#f43f5e;">🆕</div>
            <div class="cc-info">
              <span class="cc-title">Novo Projeto</span>
              <span class="cc-sub">Limpar sessão Flow</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span>Diagnóstico em Tempo Real</span>
          </div>
          <div class="sys-row">
            <span style="color:var(--text-secondary);">Fila Central (Daemon)</span>
            <span id="sysDaemon" style="font-weight:700; color:#10b981;">Online (Porta 9334)</span>
          </div>
          <div class="sys-row">
            <span style="color:var(--text-secondary);">Google Chrome CDP</span>
            <span id="sysChrome" style="font-weight:700;">Verificando...</span>
          </div>
          <div class="sys-row">
            <span style="color:var(--text-secondary);">Sessão Google Flow</span>
            <span id="sysLogin" style="font-weight:700;">Verificando...</span>
          </div>
          <div class="sys-row">
            <span style="color:var(--text-secondary);">Visibilidade Atual</span>
            <span id="sysVis" style="font-weight:700; color:#10b981;">Off-Screen Invisível</span>
          </div>
        </div>

        <button class="btn btn-glass" style="width:100%; padding:9px;" onclick="runDiagnose()">
          🩺 Executar Auto-Healing Snapshot (DOM + Rede)
        </button>
      </div>

    </div>
  </div>

  <div id="toast">Pronto</div>

  <script>
    const API = "http://127.0.0.1:9334";
    let singleType = 'video';

    const MODELS_VIDEO = [
      { id: "lower_priority", name: "Veo 3.1 - Lite [Lower Priority]" },
      { id: "lite", name: "Veo 3.1 - Lite" },
      { id: "fast", name: "Veo 3.1 - Fast" },
      { id: "quality", name: "Veo 3.1 - Quality" },
      { id: "omni", name: "Omni 1.1 Flash" }
    ];
    const MODELS_IMAGE = [
      { id: "2.1", name: "Nano Banana 2.1" },
      { id: "pro", name: "Nano Banana Pro" },
      { id: "lite", name: "Nano Banana 2 Lite" }
    ];

    function toast(msg) {
      const el = document.getElementById('toast');
      el.innerText = msg;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 2200);
    }

    async function safeFetch(path, options = {}, timeoutMs = 8000) {
      const ctrl = new AbortController();
      const id = setTimeout(() => ctrl.abort(), timeoutMs);
      try {
        const res = await fetch(API + path, { ...options, signal: ctrl.signal });
        clearTimeout(id);
        return await res.json();
      } catch (e) {
        clearTimeout(id);
        return null;
      }
    }

    function switchTab(tab) {
      ['queue', 'create', 'batch', 'status'].forEach(t => {
        document.getElementById('nav-' + t).classList.toggle('active', t === tab);
        document.getElementById('tab-' + t).classList.toggle('active', t === tab);
      });
      if (tab === 'queue') refreshQueue();
      if (tab === 'status') refreshHealth();
    }

    function setSingleType(t) {
      singleType = t;
      document.getElementById('optVideo').classList.toggle('active', t === 'video');
      document.getElementById('optImage').classList.toggle('active', t === 'imagem');
      document.getElementById('singleVideoExtras').style.display = t === 'video' ? 'grid' : 'none';
      const sel = document.getElementById('singleModel');
      sel.innerHTML = (t === 'video' ? MODELS_VIDEO : MODELS_IMAGE)
        .map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    }

    function syncBatchModels() {
      const t = document.getElementById('batchType').value;
      const sel = document.getElementById('batchModel');
      sel.innerHTML = (t === 'video' ? MODELS_VIDEO : MODELS_IMAGE)
        .map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    }

    function updateBatchCounter() {
      const raw = document.getElementById('batchText').value || '';
      const lines = raw.split('\n').map(x => x.trim()).filter(x => x && !x.startsWith('#'));
      document.getElementById('batchCounter').innerText = `${lines.length} prompts`;
    }

    function handleTxtUpload(ev) {
      const f = ev.target.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = e => {
        document.getElementById('batchText').value = e.target.result;
        updateBatchCounter();
        toast(`Arquivo ${f.name} carregado!`);
      };
      reader.readAsText(f);
    }

    async function refreshQueue() {
      const data = await safeFetch('/queue');
      if (!data || !data.ok) return;

      const totalActive = (data.queued ? data.queued.length : 0) + (data.running ? data.running.length : 0);
      document.getElementById('badgeQueue').innerText = totalActive;
      document.getElementById('queuedCountText').innerText = `${data.queued.length} na fila`;

      // Running card
      const rCard = document.getElementById('runningCard');
      if (data.running && data.running.length > 0) {
        const r = data.running[0];
        rCard.style.display = 'block';
        const proj = r.workspace ? r.workspace.split(/[\\/]/).pop() : 'Geral';
        document.getElementById('runningProj').innerText = proj;
        document.getElementById('runningBody').innerHTML = `
          <div style="font-weight:600; margin-bottom:4px;">${r.prompt || ''}</div>
          <div class="tags">
            <span class="tag ${r.tipo === 'imagem' ? 'tag-img' : 'tag-vid'}">${r.tipo}</span>
            <span class="tag tag-prio">${r.modelo || 'Padrão'}</span>
            <span class="tag tag-proj">${r.status}</span>
          </div>
        `;
      } else {
        rCard.style.display = 'none';
      }

      // Projects Priority Card
      const pCard = document.getElementById('projectsCard');
      const pList = document.getElementById('projectsList');
      if (data.projects && data.projects.length > 0) {
        pCard.style.display = 'block';
        pList.innerHTML = data.projects.map(p => {
          const isHigh = p.highest_priority < 50;
          const safeWs = (p.workspace || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
          return `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.3); padding:6px 10px; border-radius:8px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span class="tag tag-proj">${p.name}</span>
                <span style="font-size:11px; color:#cbd5e1;">${p.count} na fila</span>
                ${isHigh ? '<span class="tag tag-prio">⚡ PRIORITÁRIO</span>' : ''}
              </div>
              <button class="btn btn-xs btn-amber" onclick="bumpProject('${safeWs}')">⚡ Dar Prioridade</button>
            </div>
          `;
        }).join('');
      } else {
        pCard.style.display = 'none';
      }

      // Queued items
      const qList = document.getElementById('queuedList');
      if (!data.queued || data.queued.length === 0) {
        qList.innerHTML = `
          <div style="text-align:center; padding:16px 8px; color:var(--text-dim); font-size:11.5px;">
            Nenhum vídeo ou imagem aguardando na fila.<br>
            <span style="font-size:10px;">Qualquer geração disparada pelos seus MCPs aparece aqui ao vivo!</span>
          </div>`;
      } else {
        qList.innerHTML = data.queued.map(j => {
          const proj = j.workspace ? j.workspace.split(/[\\/]/).pop() : 'Geral';
          const isHigh = (j.priority || 100) < 50;
          return `
            <div class="q-item">
              <div class="q-top">
                <div class="tags">
                  <span class="tag ${j.tipo === 'imagem' ? 'tag-img' : 'tag-vid'}">${j.tipo}</span>
                  <span class="tag tag-proj">${proj}</span>
                  ${isHigh ? '<span class="tag tag-prio">⚡ ALTA</span>' : ''}
                </div>
                <span style="font-size:10px; color:var(--text-dim);">${(j.created_at || '').slice(11, 19)}</span>
              </div>
              <div class="q-prompt">${j.prompt || ''}</div>
              <div class="q-actions">
                ${!isHigh ? `<button class="btn btn-xs btn-glass" onclick="bumpJob('${j.job_id}')">⬆️ Subir</button>` : ''}
                <button class="btn btn-xs btn-rose" onclick="cancelJob('${j.job_id}')">✕ Cancelar</button>
              </div>
            </div>
          `;
        }).join('');
      }

      // Completed items
      const cList = document.getElementById('completedList');
      if (!data.recent_completed || data.recent_completed.length === 0) {
        cList.innerHTML = '<div style="font-size:11px; color:var(--text-dim);">Nenhuma mídia finalizada ainda.</div>';
      } else {
        cList.innerHTML = data.recent_completed.slice(0, 5).map(c => {
          const proj = c.workspace ? c.workspace.split(/[\\/]/).pop() : 'MCP';
          return `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:11px;">
              <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:270px; color:#cbd5e1;">
                ✅ <strong style="color:#fff;">[${proj}]</strong> ${c.prompt || c.file_path}
              </div>
              <span class="tag tag-img">SALVO</span>
            </div>
          `;
        }).join('');
      }
    }

    async function refreshHealth() {
      const h = await safeFetch('/health');
      const dot = document.getElementById('topDot');
      const txt = document.getElementById('topStatusText');

      if (!h || !h.ok) {
        dot.style.background = '#ef4444';
        txt.innerText = 'Daemon Reconectando...';
        return;
      }

      document.getElementById('sysChrome').innerHTML = h.browser_connected
        ? '<span style="color:#10b981;">Conectado (Porta 9333)</span>'
        : '<span style="color:#94a3b8;">Standby (Abre ao gerar)</span>';

      document.getElementById('sysLogin').innerHTML = h.login_completed_marker
        ? '<span style="color:#10b981;">Autenticado ✓</span>'
        : '<span style="color:#f59e0b;">Requer Login Inicial</span>';

      document.getElementById('sysVis').innerHTML = h.browser_hidden
        ? '<span style="color:#10b981;">Invisível (Off-Screen + Sem Ícone)</span>'
        : '<span style="color:#f59e0b;">Visível na Tela</span>';

      if (h.active_job_id) {
        dot.style.background = '#f59e0b';
        dot.style.boxShadow = '0 0 8px #f59e0b';
        txt.innerText = 'Renderizando no Flow...';
      } else {
        dot.style.background = '#10b981';
        dot.style.boxShadow = '0 0 8px #10b981';
        txt.innerText = 'Pronto • Modo Invisível';
      }
    }

    function refreshAll() {
      refreshQueue();
      refreshHealth();
      toast('Atualizado!');
    }

    async function submitSingle() {
      const prompt = document.getElementById('singlePrompt').value.trim();
      if (!prompt) return toast('Digite um prompt primeiro!');

      const payload = {
        prompt,
        tipo: singleType,
        modelo: document.getElementById('singleModel').value,
        proporcao: document.getElementById('singleRatio').value,
        duracao: document.getElementById('singleDur').value,
        resolucao: document.getElementById('singleRes').value,
        priority: parseInt(document.getElementById('singlePrio').value || '100'),
        imagem_in: document.getElementById('singleIn').value.trim(),
        imagem_out: document.getElementById('singleOut').value.trim(),
        ingredientes: document.getElementById('singleIng').value.trim(),
        output_path: document.getElementById('singlePath').value.trim(),
        workspace: 'Painel Tray',
        wait: false
      };

      toast('Adicionando à fila...');
      const res = await safeFetch('/enqueue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res && res.ok) {
        document.getElementById('singlePrompt').value = '';
        toast('Adicionado à Fila Central!');
        switchTab('queue');
      } else {
        toast('Erro ao adicionar na fila');
      }
    }

    async function submitBatch() {
      const raw = document.getElementById('batchText').value || '';
      const lines = raw.split('\n').map(x => x.trim()).filter(x => x && !x.startsWith('#'));
      if (lines.length === 0) return toast('Cole ou suba pelo menos 1 prompt!');

      const tipo = document.getElementById('batchType').value;
      const modelo = document.getElementById('batchModel').value;
      const proporcao = document.getElementById('batchRatio').value;
      const priority = parseInt(document.getElementById('batchPrio').value || '100');
      const output_path = document.getElementById('batchPath').value.trim();

      const items = lines.map(p => ({
        prompt: p,
        tipo,
        modelo,
        proporcao,
        priority,
        output_path,
        workspace: 'Lote TXT',
        wait: false
      }));

      toast(`Enfileirando ${items.length} itens...`);
      const res = await safeFetch('/enqueue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items, wait: false })
      }, 15000);

      if (res && res.ok) {
        document.getElementById('batchText').value = '';
        updateBatchCounter();
        toast(`${items.length} itens enviados para a fila!`);
        switchTab('queue');
      } else {
        toast('Erro ao enfileirar lote');
      }
    }

    async function bumpJob(jobId) {
      await safeFetch(`/jobs/${jobId}/priority`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority: 10 })
      });
      toast('Prioridade máxima definida!');
      refreshQueue();
    }

    async function bumpProject(workspace) {
      await safeFetch('/projects/priority', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace, priority: 10 })
      });
      toast(`Projeto priorizado na fila!`);
      refreshQueue();
    }

    async function cancelJob(jobId) {
      await safeFetch(`/jobs/${jobId}/cancel`, { method: 'POST' });
      toast('Item removido da fila');
      refreshQueue();
    }

    async function runBrowserCmd(action) {
      toast('Processando comando no navegador...');
      const res = await safeFetch(`/browser/${action}`, { method: 'POST' }, 30000);
      if (res && res.ok) {
        toast(res.visible ? 'Navegador visível na tela!' : 'Navegador oculto fora da tela!');
        refreshHealth();
      } else {
        toast('Ação concluída');
      }
    }

    async function runDiagnose() {
      toast('Inspecionando DOM e Rede do Flow...');
      const res = await safeFetch('/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ open_settings_menu: false, take_screenshot: true })
      }, 30000);
      if (res && res.ok) {
        toast('Snapshot Auto-Healing salvo com sucesso!');
      } else {
        toast('Falha ao coletar diagnóstico');
      }
    }

    // Inicializacao imediata (sem depender de bridge bloqueante)
    setSingleType('video');
    syncBatchModels();
    refreshQueue();
    refreshHealth();
    setInterval(refreshQueue, 2000);
    setInterval(refreshHealth, 3500);
  </script>
</body>
</html>
"""


class FlowStudioFlyoutController:
    """
    Controla o popup estilo Control Center usando chamadas Win32 diretas e thread-safe:
      - Remove 100% o icone do Python da barra de tarefas (WS_EX_TOOLWINDOW + ITaskbarList::DeleteTab)
      - Aplica cantos arredondados nativos do Windows 11 (DWMWA_WINDOW_CORNER_PREFERENCE)
      - Alterna (toggle) ao clicar no icone do tray e fecha sozinho ao clicar fora!
    """

    def __init__(self):
        self.window = None
        self.hwnd = None
        self.tray_icon = None
        self.is_running = True
        self.is_visible = False
        self.initial_load_done = False
        self.last_show_ts = 0.0
        self.last_hide_ts = 0.0

    def find_and_style_hwnd(self):
        """Encontra o HWND da janela do pywebview, aplica cantos redondos nativos e remove da barra de tarefas."""
        if os.name != "nt":
            return None
        user32 = ctypes.windll.user32
        ole32 = ctypes.windll.ole32
        dwmapi = ctypes.windll.dwmapi
        my_pid = os.getpid()
        found_hwnd = None

        def cb(hwnd, lparam):
            nonlocal found_hwnd
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == my_pid:
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if "Flow Studio" in buff.value:
                    found_hwnd = hwnd
                    return 0
            return 1

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(cb), 0)

        if found_hwnd:
            self.hwnd = found_hwnd
            # 1. Aplica WS_EX_TOOLWINDOW e remove WS_EX_APPWINDOW para NUNCA mostrar icone de Python na Taskbar
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            ex_style = user32.GetWindowLongW(found_hwnd, GWL_EXSTYLE)
            new_ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(found_hwnd, GWL_EXSTYLE, new_ex_style)

            # 2. Remove via ITaskbarList::DeleteTab para garantia absoluta
            try:
                ole32.CoInitialize(None)

                class GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", wintypes.DWORD),
                        ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_byte * 8),
                    ]

                CLSID_TaskbarList = GUID(
                    0x56FDF344, 0xFD6D, 0x11D0, (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90)
                )
                IID_ITaskbarList = GUID(
                    0x56FDF342, 0xFD6D, 0x11D0, (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90)
                )
                p_tbl = ctypes.c_void_p()
                if (
                    ole32.CoCreateInstance(
                        ctypes.byref(CLSID_TaskbarList), None, 1, ctypes.byref(IID_ITaskbarList), ctypes.byref(p_tbl)
                    )
                    == 0
                    and p_tbl.value
                ):
                    vtable = ctypes.cast(p_tbl, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])(p_tbl)
                    ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)(vtable[5])(p_tbl, found_hwnd)
            except Exception:
                pass

            # 3. Aplica cantos arredondados nativos do Windows 11 (DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2)
            try:
                preference = ctypes.c_int(2)
                dwmapi.DwmSetWindowAttribute(found_hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
            except Exception:
                pass

        return found_hwnd

    def toggle_popup(self, *args):
        """Chamado ao clicar no icone da bandeja: abre se fechado, recolhe se aberto."""
        # Se acabou de fechar pelo clique no proprio icone da bandeja (< 0.55s), mantem recolhido!
        if not self.is_visible and (time.time() - self.last_hide_ts) < 0.55:
            return

        if self.is_visible:
            self.hide_popup()
        else:
            self.show_popup()

    def show_popup(self):
        if os.name == "nt":
            if not self.hwnd:
                self.find_and_style_hwnd()
            if self.hwnd:
                user32 = ctypes.windll.user32
                pos_x, pos_y = get_flyout_position(POPUP_WIDTH, POPUP_HEIGHT)
                SWP_SHOWWINDOW = 0x0040
                self.last_show_ts = time.time()
                self.is_visible = True
                user32.ShowWindow(wintypes.HWND(self.hwnd), 5)  # Garante visibilidade
                self.find_and_style_hwnd()
                user32.SetWindowPos(
                    wintypes.HWND(self.hwnd),
                    wintypes.HWND(-1),
                    int(pos_x),
                    int(pos_y),
                    int(POPUP_WIDTH),
                    int(POPUP_HEIGHT),
                    SWP_SHOWWINDOW,
                )
                # Contorna o bloqueio de Foreground do Windows ao clicar na bandeja
                try:
                    user32.keybd_event(0x12, 0, 0, 0)  # ALT down
                    user32.SetForegroundWindow(wintypes.HWND(self.hwnd))
                    user32.keybd_event(0x12, 0, 2, 0)  # ALT up
                except Exception:
                    pass
                return
        if self.window:
            self.last_show_ts = time.time()
            self.is_visible = True
            self.window.show()

    def hide_popup(self, from_blur=False):
        if from_blur:
            self.last_hide_ts = time.time()
        self.is_visible = False
        if os.name == "nt":
            if not self.hwnd:
                self.find_and_style_hwnd()
            if self.hwnd:
                # Move para off-screen (-32000, -32000) mantendo o WebView2 aquecido para abrir em 0ms!
                ctypes.windll.user32.SetWindowPos(
                    wintypes.HWND(self.hwnd),
                    wintypes.HWND(0),
                    -32000,
                    -32000,
                    int(POPUP_WIDTH),
                    int(POPUP_HEIGHT),
                    0x0004 | 0x0010,
                )
                return
        if self.window:
            self.window.hide()

    def watch_outside_click_and_style(self):
        """
        Monitora de forma 100% confiavel:
        1) Garante que o HWND esteja sem icone na barra de tarefas e com cantos redondos.
        2) Quando o popup esta visivel e o usuario clica com o mouse FORA da area do popup, recolhe na hora!
        """
        user32 = ctypes.windll.user32
        my_pid = os.getpid()
        was_mouse_down = False

        while self.is_running:
            time.sleep(0.04)
            if os.name != "nt":
                continue

            if not self.hwnd:
                self.find_and_style_hwnd()
                continue

            if not self.is_visible:
                was_mouse_down = False
                continue

            # Ignora cliques nos primeiros 400ms apos abrir (para nao fechar com o proprio clique do Tray)
            if (time.time() - self.last_show_ts) < 0.40:
                continue

            lmb = (user32.GetAsyncKeyState(0x01) & 0x8000) != 0
            rmb = (user32.GetAsyncKeyState(0x02) & 0x8000) != 0
            mouse_down = lmb or rmb

            if mouse_down and not was_mouse_down:
                pt = wintypes.POINT()
                rect = wintypes.RECT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.GetWindowRect(self.hwnd, ctypes.byref(rect))

                inside = (rect.left <= pt.x <= rect.right) and (rect.top <= pt.y <= rect.bottom)
                if not inside:
                    # Verifica se a janela em foco pertence ao nosso PID (ex: janela de escolher arquivo .TXT)
                    fg = user32.GetForegroundWindow()
                    fg_pid = wintypes.DWORD()
                    if fg:
                        user32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
                    if fg != 0 and fg_pid.value == my_pid and fg != self.hwnd:
                        # Dialogo de arquivo aberto, nao fecha o popup
                        pass
                    else:
                        self.hide_popup(from_blur=True)

            was_mouse_down = mouse_down

    def trigger_browser(self, action: str):
        def _run():
            try:
                req = urllib.request.Request(
                    f"{DAEMON_URL}/browser/{action}", data=b"{}", headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=25)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def quit_all(self, *args):
        self.is_running = False
        if self.tray_icon:
            try:
                self.tray_icon.visible = False
                self.tray_icon.stop()
            except Exception:
                pass
        os._exit(0)

    def monitor_tray_status(self):
        last_status = "ready"
        while self.is_running:
            time.sleep(2.0)
            status = "ready"
            tip = "Flow Studio — Pronto"
            try:
                with urllib.request.urlopen(f"{DAEMON_URL}/health", timeout=1.5) as resp:
                    h = json.loads(resp.read().decode())
                with urllib.request.urlopen(f"{DAEMON_URL}/queue", timeout=1.5) as resp:
                    q = json.loads(resp.read().decode())

                running_cnt = len(q.get("running", []))
                queued_cnt = len(q.get("queued", []))

                if not h.get("login_completed_marker"):
                    status = "login"
                    tip = "Flow Studio — Aguardando Login Inicial"
                elif running_cnt > 0:
                    status = "rendering"
                    tip = f"Flow Studio — Renderizando ({queued_cnt} na fila)"
                else:
                    status = "ready"
                    tip = f"Flow Studio — Pronto ({queued_cnt} na fila)"
            except Exception:
                status = "offline"
                tip = "Flow Studio — Conectando ao Daemon..."

            if self.tray_icon:
                try:
                    self.tray_icon.title = tip
                    if status != last_status:
                        self.tray_icon.icon = create_tray_icon_image(status)
                        last_status = status
                except Exception:
                    pass

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("⚡ Alternar Painel Flow Studio", self.toggle_popup, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("👁️ Mostrar Navegador (/showbrowser)", lambda icon, item: self.trigger_browser("show")),
            pystray.MenuItem("👻 Esconder Navegador (/hidebrowser)", lambda icon, item: self.trigger_browser("hide")),
            pystray.MenuItem("🔑 Login Google Flow (/loginbrowser)", lambda icon, item: self.trigger_browser("login")),
            pystray.MenuItem("🆕 Novo Projeto no Flow", lambda icon, item: self.trigger_browser("new_project")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Sair do Flow Studio", self.quit_all),
        )

        self.tray_icon = pystray.Icon(
            "flow-studio",
            create_tray_icon_image("ready"),
            "Flow Studio — Pronto",
            menu,
        )
        self.tray_icon.run_detached()
        threading.Thread(target=self.monitor_tray_status, daemon=True).start()
        threading.Thread(target=self.watch_outside_click_and_style, daemon=True).start()


class LightweightBridge:
    def __init__(self, ctrl: FlowStudioFlyoutController):
        self._ctrl = ctrl

    def close_flyout(self):
        self._ctrl.hide_popup()
        return {"ok": True}


def enforce_single_tray_instance():
    """Garante que apenas 1 instancia do flow_tray.py rode por vez para nao duplicar icones na bandeja."""
    pid_dir = Path("C:/flow-mcp-profile") if os.name == "nt" else Path.home() / ".flow-studio-profile"
    pid_dir.mkdir(parents=True, exist_ok=True)
    pid_file = pid_dir / "flow_tray.pid"
    my_pid = os.getpid()

    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            if old_pid != my_pid:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(old_pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
        except Exception:
            pass

    try:
        pid_file.write_text(str(my_pid))
    except Exception:
        pass


def main():
    enforce_single_tray_instance()
    ensure_daemon()
    ctrl = FlowStudioFlyoutController()
    ctrl.setup_tray()
    bridge = LightweightBridge(ctrl)

    pos_x, pos_y = get_flyout_position(POPUP_WIDTH, POPUP_HEIGHT)

    ctrl.window = webview.create_window(
        title="Flow Studio Flyout",
        html=HTML_DASHBOARD,
        js_api=bridge,
        width=POPUP_WIDTH,
        height=POPUP_HEIGHT,
        x=pos_x,
        y=pos_y,
        resizable=False,
        frameless=True,
        easy_drag=True,
        on_top=True,
    )

    def on_shown():
        ctrl.find_and_style_hwnd()
        if not ctrl.initial_load_done:
            ctrl.initial_load_done = True
            ctrl.show_popup()

    def on_closing():
        ctrl.hide_popup()
        return False

    ctrl.window.events.shown += on_shown
    ctrl.window.events.closing += on_closing

    webview.start(debug=False)


if __name__ == "__main__":
    main()
