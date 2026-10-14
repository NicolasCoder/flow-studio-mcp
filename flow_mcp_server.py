import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union
import aiohttp
from mcp.server.fastmcp import FastMCP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DAEMON_SCRIPT = os.path.join(BASE_DIR, "flow_queue_daemon.py")
DAEMON_PORT = int(os.environ.get("FLOW_DAEMON_PORT", "9334"))
DAEMON_URL = f"http://127.0.0.1:{DAEMON_PORT}"

mcp = FastMCP("flow-studio")


async def ensure_daemon_running() -> Dict[str, Any]:
    """
    Verifica se o daemon central de fila unica (porta 9334) esta ativo.
    Se nao estiver, inicia automaticamente em background fora de qualquer Job Object
    para que todos os projetos compartilhem a mesma fila global.
    """
    timeout = aiohttp.ClientTimeout(total=3)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(f"{DAEMON_URL}/health") as resp:
                if resp.status == 200:
                    return await resp.json()
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
            [sys.executable, DAEMON_SCRIPT],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for _ in range(25):
            await asyncio.sleep(0.5)
            try:
                async with session.get(f"{DAEMON_URL}/health") as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                pass

    raise RuntimeError(f"Nao foi possivel iniciar ou conectar ao Flow Central Queue Daemon na porta {DAEMON_PORT}.")


async def daemon_request(method: str, path: str, payload: Optional[dict] = None, timeout_sec: float = 660.0) -> dict:
    await ensure_daemon_running()
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        url = f"{DAEMON_URL}{path}"
        if method.upper() == "GET":
            async with session.get(url) as resp:
                return await resp.json()
        else:
            async with session.post(url, json=payload or {}) as resp:
                return await resp.json()


@mcp.tool()
async def flow_generate(
    prompt: str,
    tipo: str = "video",
    output_path: str = "",
    modelo: str = "",
    proporcao: str = "16:9",
    duracao: str = "8s",
    resolucao: str = "720p",
    quantidade: str = "x1",
    frame_in: str = "",
    frame_out: str = "",
    swap_frames: bool = False,
    ingredientes: Optional[Union[List[str], str]] = None,
    workspace: str = "",
    wait: bool = True,
) -> Dict[str, Any]:
    """
    Envia uma geracao de VIDEO ou IMAGEM para a fila central unica do Google Flow e faz o download automatico.
    Se ocorrer qualquer erro de seletor ou RPC, retorna automaticamente um pacote `diagnostics` para Auto-Healing.

    Args:
        prompt: Descricao detalhada do video ou imagem a ser gerado.
        tipo: "video" ou "imagem".
        output_path: Caminho completo do arquivo de saida (ex: "C:/projeto/cena1.mp4") ou pasta de destino.
        modelo:
            - Para video: "lower_priority" (Veo 3.1 - Lite [Lower Priority]), "lite" (Veo 3.1 - Lite),
              "fast" (Veo 3.1 - Fast), "quality" (Veo 3.1 - Quality), "omni" (Omni 1.1 Flash).
            - Para imagem: "2.1" (Nano Banana 2.1), "pro" (Nano Banana Pro), "lite" (Nano Banana 2 Lite).
        proporcao: "16:9", "9:16", "4:3", "1:1" ou "3:4".
        duracao: "4s", "6s", "8s" ou "10s" (aplicavel para video).
        resolucao: "720p" ou "360p" (aplicavel para video).
        quantidade: "x1", "x2", "x3" ou "x4".
        frame_in: Caminho local da imagem inicial (Start Frame) para Image-to-Video.
        frame_out: Caminho local da imagem final (End Frame) para Image-to-Video.
        swap_frames: Se True, inverte os frames inicial e final no Flow.
        ingredientes: Lista de caminhos de imagens locais (ou string separada por virgula) para usar como Ingredientes.
        workspace: Diretorio do projeto atual (opcional, ajuda a resolver caminhos relativos).
        wait: Se True (padrao), aguarda na fila ate o arquivo ser baixado e retorna file_path e media_id.
    """
    ings_list: List[str] = []
    if isinstance(ingredientes, str) and ingredientes.strip():
        ings_list = [x.strip() for x in ingredientes.split(",") if x.strip()]
    elif isinstance(ingredientes, list):
        ings_list = [str(x).strip() for x in ingredientes if str(x).strip()]

    payload = {
        "prompt": prompt,
        "tipo": tipo,
        "output_path": output_path,
        "modelo": modelo,
        "proporcao": proporcao,
        "duracao": duracao,
        "resolucao": resolucao,
        "quantidade": quantidade,
        "imagem_in": frame_in,
        "imagem_out": frame_out,
        "swap_frames": swap_frames,
        "ingredientes": ings_list,
        "workspace": workspace or os.getcwd(),
        "wait": wait,
    }
    res = await daemon_request("POST", "/enqueue", payload, timeout_sec=700.0 if wait else 30.0)
    job = res.get("job", {})
    return {
        "ok": res.get("ok", False),
        "job_id": job.get("job_id"),
        "media_id": job.get("media_id"),
        "file_path": job.get("file_path"),
        "status": job.get("status"),
        "error": job.get("error"),
        "diagnostics": job.get("diagnostics"),
        "job": job,
    }


@mcp.tool()
async def flow_generate_batch(
    items: List[Dict[str, Any]],
    workspace: str = "",
    wait: bool = True,
) -> Dict[str, Any]:
    """
    Enfileira varios videos e/ou imagens de uma so vez na fila central unica do Google Flow.
    """
    ws = workspace or os.getcwd()
    norm_items = []
    for it in items:
        copy_it = dict(it)
        copy_it.setdefault("workspace", ws)
        norm_items.append(copy_it)

    return await daemon_request(
        "POST",
        "/enqueue",
        {"items": norm_items, "wait": wait, "timeout": 1800},
        timeout_sec=1850.0 if wait else 30.0,
    )


@mcp.tool()
async def flow_queue_status(
    job_id: str = "",
    wait: bool = False,
) -> Dict[str, Any]:
    """
    Consulta o status da fila central unica (compartilhada entre todos os projetos)
    ou consulta/aguarda um `job_id` especifico.
    """
    if job_id.strip():
        q = "?wait=1" if wait else ""
        return await daemon_request("GET", f"/jobs/{job_id.strip()}{q}", timeout_sec=650.0 if wait else 15.0)
    return await daemon_request("GET", "/queue", timeout_sec=15.0)


@mcp.tool()
async def flow_login_browser() -> Dict[str, Any]:
    """
    Abre ou traz para a tela o Google Chrome isolado do Flow (porta 9333)
    em modo VISIVEL para o usuario fazer o primeiro login na conta Google / Google Flow.
    Apos logar e fechar (ou ocultar), todas as proximas execucoes rodarao invisiveis fora da tela.
    """
    return await daemon_request("POST", "/browser/login", timeout_sec=45.0)


@mcp.tool()
async def flow_show_browser() -> Dict[str, Any]:
    """
    Traz imediatamente a janela do Google Chrome do Flow para a tela (X=100, Y=80)
    para que o usuario possa visualizar o navegador em tempo real (/showbrowser).
    """
    return await daemon_request("POST", "/browser/show", timeout_sec=30.0)


@mcp.tool()
async def flow_hide_browser() -> Dict[str, Any]:
    """
    Esconde imediatamente a janela do Google Chrome do Flow para fora da tela (X=-2400, Y=0),
    mantendo a automacao rodando 100% invisivel sem interromper nenhuma geracao (/hidebrowser).
    """
    return await daemon_request("POST", "/browser/hide", timeout_sec=30.0)


@mcp.tool()
async def flow_new_project() -> Dict[str, Any]:
    """
    Forca a criacao de um novo projeto limpo dentro do Google Flow.
    """
    return await daemon_request("POST", "/browser/new_project", timeout_sec=45.0)


@mcp.tool()
async def flow_diagnose(
    open_settings_menu: bool = False,
    take_screenshot: bool = True,
) -> Dict[str, Any]:
    """
    [AUTO-HEALING TOOL] Inspeciona a pagina ao vivo do Google Flow quando algum seletor, botao,
    modelo ou RPC mudar no site. Retorna todos os botoes visiveis, aria-labels, tags customizadas
    (<flow-*>), chamadas de rede `batchexecute` recentes (com os `rpcids` atuais), os seletores
    atuais de `selectors.json` e o caminho de um screenshot atualizado da pagina.
    """
    return await daemon_request(
        "POST",
        "/diagnose",
        {"open_settings_menu": open_settings_menu, "take_screenshot": take_screenshot},
        timeout_sec=45.0,
    )


@mcp.tool()
async def flow_update_selectors(
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    [AUTO-HEALING TOOL] Atualiza `selectors.json` em tempo real (sem precisar reiniciar o daemon).
    Permite corrigir seletores CSS/Playwright (`selectors`), IDs de RPC (`rpc_ids`) ou nomes de
    modelos (`video_models`, `image_models`) assim que o agente detectar mudancas via `flow_diagnose`.
    """
    return await daemon_request("POST", "/selectors", updates, timeout_sec=20.0)


@mcp.tool()
async def flow_reload_daemon() -> Dict[str, Any]:
    """
    [AUTO-HEALING TOOL] Recarrega o modulo `flowapi.py` e `selectors.json` em memoria dentro do
    daemon central em execucao. Use apos editar `flowapi.py` ou `selectors.json` para aplicar
    as correcoes imediatamente sem perder a fila atual.
    """
    return await daemon_request("POST", "/reload", {}, timeout_sec=20.0)


if __name__ == "__main__":
    mcp.run()

