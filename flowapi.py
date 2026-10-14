import asyncio
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELECTORS_PATH = os.path.join(BASE_DIR, "selectors.json")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DIAGNOSTICS_DIR = os.path.join(BASE_DIR, "diagnostics")

# ==========================================
# PERFIL ISOLADO MULTIPLATAFORMA E PORTA CDP
# ==========================================
CHROME_PORT = int(os.environ.get("FLOW_CHROME_PORT", "9333"))


def obter_diretorio_perfil() -> str:
    env_dir = os.environ.get("FLOW_PROFILE_DIR")
    if env_dir:
        return env_dir
    # Preserva C:\flow-mcp-profile se ja existir no Windows, senao usa ~/.flow-studio-profile
    if os.name == "nt" and os.path.exists(r"C:\flow-mcp-profile"):
        return r"C:\flow-mcp-profile"
    return os.path.join(os.path.expanduser("~"), ".flow-studio-profile")


CHROME_PROFILE_DIR = obter_diretorio_perfil()
LOGIN_MARKER_FILE = os.path.join(CHROME_PROFILE_DIR, ".login_completed")


def ja_fez_login_inicial() -> bool:
    return os.path.exists(LOGIN_MARKER_FILE)


def marcar_login_concluido():
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    with open(LOGIN_MARKER_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat())


def detectar_executavel_chrome() -> str:
    """Detecta o executavel do Google Chrome em qualquer computador (Windows, macOS ou Linux)."""
    env_chrome = os.environ.get("FLOW_CHROME_EXE")
    if env_chrome and os.path.exists(env_chrome):
        return env_chrome

    sistema = platform.system().lower()
    candidatos = []
    if sistema == "windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        prog_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidatos = [
            os.path.join(prog_files, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(prog_x86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(local_app, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(prog_files, r"Google\Chrome Beta\Application\chrome.exe"),
        ]
    elif sistema == "darwin":
        candidatos = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        ]
    else:
        for cmd in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            achado = shutil.which(cmd)
            if achado:
                candidatos.append(achado)

    for c in candidatos:
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError(
        "Google Chrome nao encontrado automaticamente. Defina a variavel de ambiente FLOW_CHROME_EXE."
    )


# ==========================================
# HOT-RELOAD DE SELETORES E RPCs (AUTO-HEALING)
# ==========================================
DEFAULT_SELECTORS = {
    "rpc_ids": {
        "video_generate": ["YhhmEf", "eb1hJf"],
        "image_generate": ["ogiZ0b"],
        "status_poll": "jwpduf",
    },
    "selectors": {
        "new_project_btn": 'button:has-text("New project"), button:has-text("Novo projeto"), a:has-text("New project"), a:has-text("Novo projeto")',
        "prompt_editor": ".ProseMirror",
        "clear_prompt_btn": 'button[aria-label="Clear prompt"], button[aria-label="Limpar prompt"]',
        "image_ingredient_chip": 'button[aria-label="Image ingredient"]',
        "settings_trigger": '[aria-label="Settings trigger"], [aria-label*="Configura"], button:has-text("crop_")',
        "tab_image": '.cdk-overlay-container button:has-text("Image"), .cdk-overlay-container button:has-text("Imagem")',
        "tab_video": '.cdk-overlay-container button:has-text("Video"), .cdk-overlay-container button:has-text("Vídeo")',
        "submode_frames": '.cdk-overlay-container button:has-text("Frames"), .cdk-overlay-container button:has-text("Quadros")',
        "submode_ingredients": '.cdk-overlay-container button:has-text("Ingredients"), .cdk-overlay-container button:has-text("Ingredientes")',
        "model_dropdown": '.cdk-overlay-container button:has-text("arrow_drop_down")',
        "model_options": '.cdk-overlay-container [role="menuitem"], .cdk-overlay-container button',
        "slot_start_frame": 'button:text-is("Start"), button:has-text("Start")',
        "slot_end_frame": 'button:text-is("End"), button:has-text("End")',
        "swap_frames_btn": 'button[aria-label="Swap first and last frames"]',
        "slot_ingredients": '[aria-label="Add ingredients to the prompt box"]',
        "upload_media_btn": '.cdk-overlay-container button:has-text("Upload media"), .cdk-overlay-container button:has-text("Upload"), .cdk-overlay-container [role="menuitem"]:has-text("Upload")',
        "start_generation_btn": '[aria-label="Start generation"], [aria-label="Iniciar geração"], button:has(mat-icon:text("arrow_forward"))',
        "image_tile_img": "flow-image-tile img",
        "video_tile": "flow-video-tile",
    },
    "video_models": {
        "lower_priority": "Veo 3.1 - Lite [Lower Priority]",
        "low_priority": "Veo 3.1 - Lite [Lower Priority]",
        "lite_low": "Veo 3.1 - Lite [Lower Priority]",
        "veo_3_1_t2v_lite_low_priority": "Veo 3.1 - Lite [Lower Priority]",
        "lite": "Veo 3.1 - Lite",
        "veo_lite": "Veo 3.1 - Lite",
        "fast": "Veo 3.1 - Fast",
        "veo_fast": "Veo 3.1 - Fast",
        "quality": "Veo 3.1 - Quality",
        "veo_quality": "Veo 3.1 - Quality",
        "omni": "Omni 1.1 Flash",
        "flash": "Omni 1.1 Flash",
        "abra_t2v_8s": "Omni 1.1 Flash",
    },
    "image_models": {
        "2.1": "Nano Banana 2.1",
        "nano_2.1": "Nano Banana 2.1",
        "pro": "Nano Banana Pro",
        "nano_pro": "Nano Banana Pro",
        "lite": "Nano Banana 2 Lite",
        "nano_lite": "Nano Banana 2 Lite",
    },
}


def carregar_seletores() -> dict:
    """Recarrega selectors.json em tempo real para permitir Auto-Healing sem reiniciar processos."""
    dados = json.loads(json.dumps(DEFAULT_SELECTORS))
    if os.path.exists(SELECTORS_PATH):
        try:
            with open(SELECTORS_PATH, "r", encoding="utf-8") as f:
                custom = json.load(f)
                for k, v in custom.items():
                    if isinstance(v, dict) and k in dados:
                        dados[k].update(v)
                    else:
                        dados[k] = v
        except Exception as e:
            print(f"[!] Aviso ao ler selectors.json: {e}")
    return dados


def atualizar_seletores(novos_dados: dict) -> dict:
    atual = carregar_seletores()
    for k, v in novos_dados.items():
        if isinstance(v, dict) and k in atual and isinstance(atual[k], dict):
            atual[k].update(v)
        else:
            atual[k] = v
    with open(SELECTORS_PATH, "w", encoding="utf-8") as f:
        json.dump(atual, f, indent=2, ensure_ascii=False)
    return atual


def carregar_config() -> dict:
    padrao = {
        "processos_simultaneos": 1,
        "espera_minima": 5,
        "espera_maxima": 14,
        "modo_invisivel": True,
        "criar_novo_projeto": True,
        "modo": "auto",
        "submodo_video": "auto",
        "modelo_video": "Veo 3.1 - Lite [Lower Priority]",
        "modelo_imagem": "Nano Banana 2.1",
        "proporcao": "16:9",
        "duracao": "8s",
        "resolucao": "720p",
        "quantidade": "x1",
        "imagem_in": "",
        "imagem_out": "",
        "ingredientes": [],
    }
    for p in ("config.json", CONFIG_PATH):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    padrao.update(json.load(f))
                break
            except Exception:
                pass
    return padrao


def resolver_nome_modelo(nome, tipo):
    sels = carregar_seletores()
    if not nome:
        return "Veo 3.1 - Lite [Lower Priority]" if tipo == "video" else "Nano Banana 2.1"
    chave = nome.strip().lower()
    mapa = sels["video_models"] if tipo == "video" else sels["image_models"]
    return mapa.get(chave, nome.strip())


def resolver_caminho_midia(caminho):
    if not caminho:
        return None
    caminho = caminho.strip().strip('"').strip("'")
    if os.path.exists(caminho):
        return os.path.abspath(caminho)
    for pasta in (
        "imagens_geradas",
        "videos_gerados",
        os.path.join(BASE_DIR, "imagens_geradas"),
        os.path.join(BASE_DIR, "videos_gerados"),
    ):
        cand = os.path.join(pasta, caminho)
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return os.path.abspath(caminho)


# ==========================================
# DIAGNOSTICO AUTO-HEALING PARA AGENTES DE IA
# ==========================================
async def coletar_diagnostico_pagina(page, motivo="", recent_rpcs=None, take_screenshot=True) -> dict:
    """
    Coleta um snapshot completo da pagina do Flow (DOM interativo, botoes, aria-labels,
    elementos customizados <flow-*>, estado do WIZ_global_data e screenshot) para que
    qualquer Agente de IA (Antigravity, Claude Code, GPT/Codex, Cursor) consiga diagnosticar
    e corrigir seletores ou RPCs quebrados automaticamente (Auto-Healing).
    """
    os.makedirs(DIAGNOSTICS_DIR, exist_ok=True)
    screenshot_path = os.path.join(DIAGNOSTICS_DIR, "last_diagnostic_screenshot.png")
    report_path = os.path.join(DIAGNOSTICS_DIR, "last_diagnostic_report.json")

    diag = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "reason": motivo,
        "selectors_file": SELECTORS_PATH,
        "flowapi_file": os.path.abspath(__file__),
        "current_selectors": carregar_seletores(),
        "recent_network_rpcs": recent_rpcs or [],
        "page_url": None,
        "params": {},
        "dom_snapshot": {},
        "screenshot_path": None,
        "auto_healing_instructions": (
            "Se um seletor CSS/Playwright ou RPC ID mudou no Google Flow: "
            "1) Analise `dom_snapshot.buttons`, `dom_snapshot.aria_elements`, `dom_snapshot.custom_flow_tags` e `recent_network_rpcs`. "
            "2) Veja a imagem em `screenshot_path` se precisar inspecionar visualmente a UI. "
            "3) Atualize `selectors.json` usando a ferramenta MCP `flow_update_selectors` (ou editando `selectors.json` / `flowapi.py`). "
            "4) Reexecute a tarefa imediatamente."
        ),
    }

    if not page or page.is_closed():
        diag["error"] = "Page is closed or unavailable"
        return diag

    try:
        diag["page_url"] = page.url
        diag["params"] = await obter_parametros_pagina(page)
        diag["dom_snapshot"] = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="menuitem"], [role="tab"]'))
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || '').trim().slice(0, 80),
                    ariaLabel: el.getAttribute('aria-label') || '',
                    classes: (el.className || '').toString().slice(0, 80),
                    visible: el.offsetParent !== null
                }))
                .filter(b => b.visible && (b.text || b.ariaLabel));

            const editors = Array.from(document.querySelectorAll('[contenteditable="true"], textarea, input'))
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    classes: (el.className || '').toString(),
                    placeholder: el.getAttribute('placeholder') || el.getAttribute('aria-label') || ''
                }));

            const customTags = Array.from(new Set(
                Array.from(document.querySelectorAll('*'))
                    .map(el => el.tagName.toLowerCase())
                    .filter(t => t.includes('flow-') || t.includes('sandbox-') || t.includes('video') || t.includes('image'))
            ));

            const overlayText = document.querySelector('.cdk-overlay-container')?.innerText || '';
            const bodyAlertText = Array.from(document.querySelectorAll('[role="alert"], .mat-mdc-snack-bar-label, snack-bar-container'))
                .map(e => (e.innerText || '').trim())
                .filter(Boolean);

            return {
                title: document.title,
                buttons: buttons.slice(0, 120),
                editors: editors,
                custom_flow_tags: customTags,
                overlay_text: overlayText.slice(0, 1000),
                alerts_or_toasts: bodyAlertText
            };
        }""")
        if take_screenshot:
            await page.screenshot(path=screenshot_path, full_page=False)
            diag["screenshot_path"] = screenshot_path
    except Exception as e:
        diag["collect_error"] = str(e)

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(diag, f, indent=2, ensure_ascii=False)
        diag["report_path"] = report_path
    except Exception:
        pass

    return diag


# ==========================================
# CONTROLE DO NAVEGADOR CHROME E JANELA OFF-SCREEN
# ==========================================
def iniciar_chrome_flow(invisivel=True, porta=CHROME_PORT, profile_dir=CHROME_PROFILE_DIR):
    """Inicia o Google Chrome padrao em perfil isolado (Windows, macOS ou Linux)."""
    chrome_exe = detectar_executavel_chrome()
    os.makedirs(profile_dir, exist_ok=True)
    pos_arg = "--window-position=-2400,0" if invisivel else "--window-position=100,80"
    args_list = [
        f"--remote-debugging-port={porta}",
        f'--user-data-dir="{profile_dir}"' if os.name == "nt" else f"--user-data-dir={profile_dir}",
        "--window-size=1280,800",
        pos_arg,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        '"https://flow.google.com/"' if os.name == "nt" else "https://flow.google.com/",
    ]
    print(f"[*] Abrindo Google Chrome ({'MODO INVISIVEL OFF-SCREEN' if invisivel else 'VISIVEL NA TELA'}) na porta {porta}...")
    if os.name == "nt":
        cmd_str = f'"{chrome_exe}" ' + " ".join(args_list)
        ps_cmd = (
            f"Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
            f"-Arguments @{{CommandLine='{cmd_str}'}} | Out-Null"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            [chrome_exe] + args_list,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def controlar_visibilidade_taskbar(visivel: bool, porta: int = CHROME_PORT):
    """
    No Windows, oculta ou exibe o icone da janela do Chrome na barra de tarefas (Taskbar)
    usando a interface COM nativa ITaskbarList (DeleteTab / AddTab).
    Mantem a janela 100% ativa em windowState='normal' fora da tela (X=-2400)
    sem derrubar o score do reCAPTCHA Enterprise nem pausar renderizacao.
    """
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        import psutil

        user32 = ctypes.windll.user32
        ole32 = ctypes.windll.ole32

        h_default = user32.OpenDesktopW("Default", 0, False, 0x10000000)
        if h_default:
            user32.SetThreadDesktop(h_default)

        ole32.CoInitialize(None)

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_byte * 8),
            ]

        CLSID_TaskbarList = GUID(
            0x56FDF344,
            0xFD6D,
            0x11D0,
            (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90),
        )
        IID_ITaskbarList = GUID(
            0x56FDF342,
            0xFD6D,
            0x11D0,
            (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90),
        )

        p_tbl = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_TaskbarList),
            None,
            1,
            ctypes.byref(IID_ITaskbarList),
            ctypes.byref(p_tbl),
        )
        if hr != 0 or not p_tbl.value:
            return False

        vtable = ctypes.cast(p_tbl, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        hr_init = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
        hr_init(p_tbl)

        add_tab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)(vtable[4])
        del_tab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)(vtable[5])

        target_pids = set()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            if p.info["name"] == "chrome.exe":
                cmd = " ".join(p.info["cmdline"] or [])
                if f"--remote-debugging-port={porta}" in cmd:
                    target_pids.add(p.info["pid"])

        def cb(hwnd, lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in target_pids:
                len_cls = 256
                cls_name = ctypes.create_unicode_buffer(len_cls)
                user32.GetClassNameW(hwnd, cls_name, len_cls)
                if "Chrome_WidgetWin_1" in cls_name.value:
                    if visivel:
                        add_tab(p_tbl, hwnd)
                    else:
                        del_tab(p_tbl, hwnd)
            return 1

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return True
    except Exception:
        return False


iniciar_chrome_beta = iniciar_chrome_flow


async def posicionar_janela_chrome(page, invisivel=True):
    """Move a janela do Chrome para fora da tela (-2400, 0) ou para a tela (100, 80) e atualiza a barra de tarefas."""
    try:
        cdp = await page.context.new_cdp_session(page)
        win_info = await cdp.send("Browser.getWindowForTarget")
        win_id = win_info["windowId"]
        left_pos = -2400 if invisivel else 100
        top_pos = 0 if invisivel else 80
        await cdp.send(
            "Browser.setWindowBounds",
            {
                "windowId": win_id,
                "bounds": {
                    "left": left_pos,
                    "top": top_pos,
                    "width": 1280,
                    "height": 800,
                    "windowState": "normal",
                },
            },
        )
        if not invisivel:
            try:
                await cdp.send("Page.bringToFront")
            except Exception:
                pass
        await cdp.detach()

        # Controla a presenca do icone na barra de tarefas do Windows
        controlar_visibilidade_taskbar(visivel=not invisivel, porta=CHROME_PORT)
        return True
    except Exception as e:
        print(f"[!] Aviso ao posicionar janela via CDP: {e}")
        return False


async def obter_parametros_pagina(page):
    """Extrai bl, fsid, atToken e endpointPrefix da pagina do Flow."""
    params = await page.evaluate("""() => {
        const html = document.documentElement.innerHTML;
        const wiz = window.WIZ_global_data || {};
        const blMatch = html.match(/cfb2h":"(boq_labs[^"]+)"/);
        const fsidMatch = html.match(/FdrFJe":"(-?[0-9]+)"/);
        const atToken = wiz.SNlM0e || '';
        const endpointPrefix = wiz.Im6cmf || '/_/AiSandboxAngularFrontend';
        const pathname = window.location.pathname;
        const pathParts = pathname.split('/project/');
        const projectId = pathParts.length > 1 ? pathParts[1].split('/')[0] : '';
        return {
            bl: wiz.cfb2h || (blMatch ? blMatch[1] : ''),
            fsid: wiz.FdrFJe || (fsidMatch ? fsidMatch[1] : ''),
            atToken: atToken,
            endpointPrefix: endpointPrefix,
            pathname: pathname,
            projectId: projectId
        };
    }""")
    return params


async def criar_projeto(page):
    """Entra no site do Flow e clica em 'New project' / 'Novo projeto' ate abrir a tela do projeto."""
    sels = carregar_seletores()["selectors"]
    try:
        if "flow.google.com" not in page.url.lower() or "project" in page.url.lower():
            await page.goto("https://flow.google.com/", wait_until="domcontentloaded")
            await asyncio.sleep(3)

        btn = page.locator(sels["new_project_btn"]).first
        for _ in range(15):
            if await btn.count() > 0:
                await btn.click()
                break
            await asyncio.sleep(1)

        for _ in range(20):
            if "project" in page.url.lower():
                editor = page.locator(sels["prompt_editor"])
                if await editor.count() > 0:
                    await asyncio.sleep(1.5)
                    return True
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[!] Erro ao criar projeto: {e}")
    return False


async def limpar_barra_prompt(page):
    """Remove ingredientes/frames anteriores e limpa o texto da caixa de prompt."""
    sels = carregar_seletores()["selectors"]
    try:
        clear_btn = page.locator(sels["clear_prompt_btn"]).first
        if await clear_btn.count() > 0:
            await clear_btn.click()
            await asyncio.sleep(0.4)
        chips = page.locator(sels["image_ingredient_chip"])
        while await chips.count() > 0:
            await chips.first.click()
            await asyncio.sleep(0.3)
    except Exception:
        pass


async def configurar_geracao(page, item, config):
    """Configura no menu do Flow: Modo (Video/Image), Submodo (Frames/Ingredients), Modelo, Proporcao, Resolucao, Duracao e Quantidade."""
    sels = carregar_seletores()["selectors"]
    tipo = item.get("tipo", "video")
    modelo_raw = item.get("modelo") or (config.get("modelo_video") if tipo == "video" else config.get("modelo_imagem"))
    modelo_alvo = resolver_nome_modelo(modelo_raw, tipo)
    proporcao = item.get("proporcao") or config.get("proporcao", "16:9")
    duracao = item.get("duracao") or config.get("duracao", "8s")
    resolucao = item.get("resolucao") or config.get("resolucao", "720p")
    quantidade = item.get("quantidade") or config.get("quantidade", "x1")

    submodo_cfg = str(config.get("submodo_video", "auto")).lower()
    if item.get("imagem_in") or item.get("imagem_out"):
        submodo = "frames"
    elif item.get("ingredientes"):
        submodo = "ingredients"
    elif submodo_cfg in ("frames", "ingredients"):
        submodo = submodo_cfg
    else:
        submodo = "ingredients"

    try:
        await limpar_barra_prompt(page)
        btn = page.locator(sels["settings_trigger"]).first
        if await btn.count() == 0:
            return
        await btn.click()
        await asyncio.sleep(0.8)

        # 1. Selecionar aba Video ou Image
        tab_btn = page.locator(sels["tab_image"] if tipo == "imagem" else sels["tab_video"]).first
        if await tab_btn.count() > 0:
            await tab_btn.click()
            await asyncio.sleep(0.5)

        # 2. Se for Video, selecionar submodo Frames ou Ingredients
        if tipo == "video":
            sub_btn = page.locator(
                sels["submode_frames"] if submodo == "frames" else sels["submode_ingredients"]
            ).first
            if await sub_btn.count() > 0:
                await sub_btn.click()
                await asyncio.sleep(0.4)

        # 3. Selecionar Modelo no dropdown
        dropdown = page.locator(sels["model_dropdown"]).first
        if await dropdown.count() > 0:
            texto_atual = (await dropdown.inner_text()).replace("arrow_drop_down", "").strip()
            if modelo_alvo.lower() not in texto_atual.lower():
                await dropdown.click()
                await asyncio.sleep(0.8)
                opcoes = page.locator(sels["model_options"])
                total_opcoes = await opcoes.count()
                clicou = False
                for idx in range(total_opcoes - 1, -1, -1):
                    el = opcoes.nth(idx)
                    txt = (await el.inner_text()).strip()
                    if modelo_alvo.lower() == txt.replace("volume_up", "").replace("🍌", "").strip().lower():
                        await el.click()
                        clicou = True
                        break
                if not clicou:
                    for idx in range(total_opcoes - 1, -1, -1):
                        el = opcoes.nth(idx)
                        txt = (await el.inner_text()).strip()
                        if modelo_alvo.lower() in txt.lower() and "arrow_drop_down" not in txt:
                            await el.click()
                            clicou = True
                            break
                await asyncio.sleep(0.5)

        # 4. Selecionar Proporcao
        if proporcao:
            prop_btn = page.locator(f'.cdk-overlay-container button:has-text("{proporcao}")').first
            if await prop_btn.count() > 0:
                await prop_btn.click()
                await asyncio.sleep(0.3)

        # 5. Selecionar Resolucao e Duracao (apenas Video)
        if tipo == "video":
            if resolucao:
                res_btn = page.locator(f'.cdk-overlay-container button:has-text("{resolucao}")').first
                if await res_btn.count() > 0:
                    await res_btn.click()
                    await asyncio.sleep(0.3)
            if duracao:
                dur_btn = page.locator(f'.cdk-overlay-container button:text-is("{duracao}")').first
                if await dur_btn.count() > 0:
                    await dur_btn.click()
                    await asyncio.sleep(0.3)

        # 6. Selecionar Quantidade
        if quantidade:
            qtd_btn = page.locator(f'.cdk-overlay-container button:text-is("{quantidade}")').first
            if await qtd_btn.count() > 0:
                await qtd_btn.click()
                await asyncio.sleep(0.3)

        await page.keyboard.press("Escape")
        await asyncio.sleep(0.4)
    except Exception as e:
        print(f"[!] Aviso ao configurar menu do Flow: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass


async def anexar_midia_no_slot(page, seletor_botao_slot, caminho_arquivo, nome_slot="Slot"):
    sels = carregar_seletores()["selectors"]
    caminho_abs = resolver_caminho_midia(caminho_arquivo)
    if not caminho_abs or not os.path.exists(caminho_abs):
        print(f"    [!] Arquivo de {nome_slot} nao encontrado: {caminho_arquivo}")
        return False

    nome_arq = os.path.basename(caminho_abs)
    nome_sem_ext = os.path.splitext(nome_arq)[0][:25]

    try:
        slot_btn = page.locator(seletor_botao_slot).first
        if await slot_btn.count() == 0:
            return False

        await slot_btn.click()
        await asyncio.sleep(0.8)

        item_existente = page.locator(f'.cdk-overlay-container button:has-text("{nome_sem_ext}")').first
        if await item_existente.count() == 0:
            upload_btn = page.locator(sels["upload_media_btn"]).first
            if await upload_btn.count() > 0:
                async with page.expect_file_chooser(timeout=10000) as fc_info:
                    await upload_btn.click()
                fc = await fc_info.value
                await fc.set_files(caminho_abs)

                for _ in range(30):
                    await asyncio.sleep(1)
                    overlay_txt = await page.evaluate(
                        "() => document.querySelector('.cdk-overlay-container')?.innerText || ''"
                    )
                    if "Uploading" not in overlay_txt and nome_sem_ext.lower() in overlay_txt.lower():
                        break

        item_btn = page.locator(f'.cdk-overlay-container button:has-text("{nome_sem_ext}")').first
        if await item_btn.count() > 0:
            await item_btn.click()
            await asyncio.sleep(0.8)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return True
        else:
            await page.keyboard.press("Escape")
            return False
    except Exception:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def aplicar_frames_e_ingredientes(page, item):
    sels = carregar_seletores()["selectors"]
    tem_anexos = bool(item.get("imagem_in") or item.get("imagem_out") or item.get("ingredientes"))
    if tem_anexos:
        await limpar_barra_prompt(page)

    if item.get("imagem_in"):
        await anexar_midia_no_slot(page, sels["slot_start_frame"], item["imagem_in"], "Frame IN (Start)")

    if item.get("imagem_out"):
        await anexar_midia_no_slot(page, sels["slot_end_frame"], item["imagem_out"], "Frame OUT (End)")

    if item.get("swap_frames"):
        swap_btn = page.locator(sels["swap_frames_btn"]).first
        if await swap_btn.count() > 0:
            await swap_btn.click()
            await asyncio.sleep(0.4)

    for ing in item.get("ingredientes") or []:
        await anexar_midia_no_slot(page, sels["slot_ingredients"], ing, "Ingrediente")


def extrair_media_id_video(body):
    sels = carregar_seletores()
    video_rpcs = tuple(sels["rpc_ids"]["video_generate"] + [sels["rpc_ids"]["status_poll"]])
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("[") and any(rpc in line for rpc in video_rpcs):
            try:
                parsed = json.loads(line)
                rpc_id = parsed[0][1]
                inner_str = parsed[0][2]
                if inner_str:
                    inner = json.loads(inner_str)
                    if rpc_id in sels["rpc_ids"]["video_generate"]:
                        if inner and len(inner) > 3 and inner[3]:
                            return inner[3][0][0], None
                    elif rpc_id == sels["rpc_ids"]["status_poll"]:
                        if inner and len(inner) > 2 and inner[2]:
                            return inner[2][0][0], None
                else:
                    error_info = parsed[0][5] if len(parsed[0]) > 5 else None
                    return None, error_info
            except Exception as e:
                return None, str(e)
    return None, "Padrao de Media ID nao encontrado na resposta"


def extrair_media_id_ogiz0b(body, project_id):
    sels = carregar_seletores()
    img_rpcs = sels["rpc_ids"]["image_generate"]
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("[") and any(rpc in line for rpc in img_rpcs):
            try:
                parsed = json.loads(line)
                inner_str = parsed[0][2]
                if not inner_str:
                    error_info = parsed[0][5] if len(parsed[0]) > 5 else None
                    return None, error_info
                uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", inner_str)
                for u in uuids:
                    if u.lower() != project_id.lower():
                        return u, None
            except Exception as e:
                return None, str(e)
    return None, "Padrao ogiZ0b nao encontrado na resposta"


async def gerar_video(page, item, params):
    sels_all = carregar_seletores()
    sels = sels_all["selectors"]
    video_rpcs = sels_all["rpc_ids"]["video_generate"]
    prompt = item.get("prompt", "")
    try:
        await aplicar_frames_e_ingredientes(page, item)

        editor = page.locator(sels["prompt_editor"]).first
        await editor.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await editor.fill(prompt)
        await asyncio.sleep(0.5)

        gen_btn = page.locator(sels["start_generation_btn"]).first

        def is_video_gen_rpc(r):
            return any(f"rpcids={rpc}" in r.url for rpc in video_rpcs)

        async with page.expect_response(is_video_gen_rpc, timeout=30000) as resp_info:
            await gen_btn.click()

        resp = await resp_info.value
        if resp.status != 200:
            return None

        body = await resp.text()
        media_id, _ = extrair_media_id_video(body)
        return media_id
    except Exception as e:
        print(f"[X] Erro ao disparar geracao de video: {e}")
        return None


URLS_IMAGEM_POR_ID = {}


async def gerar_imagem(page, item, params):
    sels_all = carregar_seletores()
    sels = sels_all["selectors"]
    img_rpcs = sels_all["rpc_ids"]["image_generate"]
    img_tile_sel = sels["image_tile_img"]
    prompt = item.get("prompt", "")
    try:
        srcs_antes = set(
            await page.evaluate(
                f"""() => {{
            return Array.from(document.querySelectorAll('{img_tile_sel}'))
                .map(img => img.src)
                .filter(Boolean);
        }}"""
            )
        )

        await aplicar_frames_e_ingredientes(page, item)

        editor = page.locator(sels["prompt_editor"]).first
        await editor.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await editor.fill(prompt)
        await asyncio.sleep(0.5)

        gen_btn = page.locator(sels["start_generation_btn"]).first

        def is_img_gen_rpc(r):
            return any(f"rpcids={rpc}" in r.url for rpc in img_rpcs)

        async with page.expect_response(is_img_gen_rpc, timeout=60000) as resp_info:
            await gen_btn.click()

        resp = await resp_info.value
        if resp.status != 200:
            return None

        body = await resp.text()
        media_id, _ = extrair_media_id_ogiz0b(body, params.get("projectId", ""))

        novo_src = None
        dom_id = None
        for _ in range(35):
            await asyncio.sleep(1)
            infos = await page.evaluate(
                f"""() => {{
                return Array.from(document.querySelectorAll('{img_tile_sel}')).map(img => ({{
                    src: img.src || '',
                    id: img.getAttribute('data-media-id') || ''
                }})).filter(x => x.src && !x.src.includes('perlin.png'));
            }}"""
            )
            for info in infos:
                if info["src"] not in srcs_antes:
                    novo_src = info["src"]
                    dom_id = info["id"]
                    break
            if novo_src:
                break

        final_id = dom_id or media_id or (f"img_{random.randint(100000, 999999)}" if novo_src else None)
        if final_id and novo_src:
            URLS_IMAGEM_POR_ID[final_id] = novo_src
        return final_id
    except Exception as e:
        print(f"[X] Erro ao disparar geracao de imagem: {e}")
        return None


async def checar_status(page, media_id, params, tipo="video"):
    sels_all = carregar_seletores()
    poll_rpc = sels_all["rpc_ids"]["status_poll"]
    if tipo == "imagem":
        if media_id in URLS_IMAGEM_POR_ID:
            return True, URLS_IMAGEM_POR_ID[media_id]
        img_src = await page.evaluate(
            """(mId) => {
            const img = document.querySelector(`img[data-media-id="${mId}"], flow-image-tile img[src*="${mId}"]`);
            return img ? img.src : null;
        }""",
            media_id,
        )
        if img_src:
            URLS_IMAGEM_POR_ID[media_id] = img_src
            return True, img_src
        return False, None

    video_src = await page.evaluate(
        """(mId) => {
        const v = document.querySelector(`video[src*="${mId}"]`);
        return v ? v.src : null;
    }""",
        media_id,
    )
    if video_src and ("flow-content.google" in video_src or "/asb/" in video_src):
        return True, video_src

    result = await page.evaluate(
        """async (args) => {
        const [mediaId, bl, fsid, atToken, endpointPrefix, pathname, pollRpc] = args;
        const innerPayload = [null, null, [[mediaId]]];
        const fReq = [[[pollRpc, JSON.stringify(innerPayload), null, "generic"]]];
        const body = `f.req=${encodeURIComponent(JSON.stringify(fReq))}&at=${encodeURIComponent(atToken)}&`;
        const url = `${endpointPrefix}/data/batchexecute?rpcids=${pollRpc}&source-path=${encodeURIComponent(pathname)}&bl=${bl}&f.sid=${fsid}&hl=en&_reqid=${Math.floor(Math.random()*9000000)+1000000}&rt=c`;
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'x-same-domain': '1'
                },
                body: body,
                credentials: 'include'
            });
            return {status: res.status, text: await res.text()};
        } catch (e) {
            return {status: 0, text: ''};
        }
    }""",
        [
            media_id,
            params["bl"],
            params["fsid"],
            params["atToken"],
            params.get("endpointPrefix", "/_/AiSandboxAngularFrontend"),
            params.get("pathname", f"/project/{params['projectId']}"),
            poll_rpc,
        ],
    )

    body = result.get("text", "")
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("[") and poll_rpc in line:
            try:
                parsed = json.loads(line)
                inner_str = parsed[0][2]
                if inner_str:
                    inner = json.loads(inner_str)
                    data_str = json.dumps(inner)
                    if "flow-content.google" in data_str:
                        return True, inner
                    try:
                        item_data = inner[2][0]
                        status_arr = item_data[5][8]
                        if status_arr == [3]:
                            return True, inner
                    except Exception:
                        pass
                    return False, inner
            except Exception:
                pass

    return False, None


URLS_VIDEO_BAIXADAS = set()


async def baixar_video(page, media_id, caminho_final, params):
    sels = carregar_seletores()["selectors"]
    video_tile_sel = sels["video_tile"]
    pasta_saida = os.path.dirname(caminho_final)
    if pasta_saida:
        os.makedirs(pasta_saida, exist_ok=True)

    try:
        video_src = None
        for _ in range(10):
            video_src = await page.evaluate(
                """(mId) => {
                const v = document.querySelector(`video[src*="${mId}"]`);
                return v ? v.src : null;
            }""",
                media_id,
            )
            if video_src:
                break

            tile = page.locator(f'flow-grid-tile-container:has([src*="{media_id}"])').first
            if await tile.count() > 0:
                try:
                    await tile.scroll_into_view_if_needed()
                    await tile.hover(force=True)
                    await asyncio.sleep(0.8)
                    video_src = await page.evaluate(
                        """(mId) => {
                        const v = document.querySelector(`video[src*="${mId}"]`);
                        return v ? v.src : null;
                    }""",
                        media_id,
                    )
                    if video_src:
                        break
                except Exception:
                    pass

            v_tiles = page.locator(video_tile_sel)
            total_vt = await v_tiles.count()
            for idx_vt in range(min(total_vt, 8)):
                try:
                    vt = v_tiles.nth(idx_vt)
                    await vt.scroll_into_view_if_needed()
                    await vt.hover(force=True)
                    await asyncio.sleep(0.8)
                    srcs = await page.evaluate(
                        f"""(mId) => {{
                        const byId = document.querySelector(`video[src*="${{mId}}"]`);
                        if (byId && byId.src) return [byId.src];
                        return Array.from(document.querySelectorAll('{video_tile_sel} video'))
                            .map(v => v.src)
                            .filter(Boolean);
                    }}""",
                        media_id,
                    )
                    for s in srcs:
                        if media_id in s or s not in URLS_VIDEO_BAIXADAS:
                            video_src = s
                            break
                    if video_src:
                        break
                except Exception:
                    pass

            if video_src:
                break
            await asyncio.sleep(1)

        if video_src:
            resp = await page.context.request.get(video_src, timeout=60000)
            data = await resp.body()
            if len(data) > 10000:
                with open(caminho_final, "wb") as f:
                    f.write(data)
                URLS_VIDEO_BAIXADAS.add(video_src)
                return True
    except Exception as e:
        print(f"    [!] Erro no download direto do video: {e}")

    return False


async def baixar_imagem(page, media_id, caminho_final, params):
    pasta_saida = os.path.dirname(caminho_final)
    if pasta_saida:
        os.makedirs(pasta_saida, exist_ok=True)

    try:
        img_src = URLS_IMAGEM_POR_ID.get(media_id)
        for _ in range(10):
            if img_src:
                break
            img_src = await page.evaluate(
                """(mId) => {
                const img = document.querySelector(`img[data-media-id="${mId}"], flow-image-tile img[src*="${mId}"]`);
                return img ? img.src : null;
            }""",
                media_id,
            )
            if img_src:
                break
            await asyncio.sleep(1)

        if img_src:
            resp = await page.context.request.get(img_src, timeout=60000)
            data = await resp.body()
            if len(data) > 1000:
                with open(caminho_final, "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"    [!] Erro no download direto da imagem: {e}")

    return False

