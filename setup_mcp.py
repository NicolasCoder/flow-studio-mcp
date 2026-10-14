#!/usr/bin/env python3
"""
Instalador Universal do Flow Studio MCP + Skill + Auto-Healing.
Funciona em qualquer computador (Windows, macOS, Linux) e configura automaticamente:
  - Google Antigravity (~/.gemini/config/mcp_config.json + Skill global)
  - Claude Code (.mcp.json + ~/.claude.json + CLAUDE.md)
  - Cursor (~/.cursor/mcp.json + .cursor/mcp.json)
  - OpenAI Codex / GPT Agents (AGENTS.md)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MCP_SERVER_SCRIPT = str(BASE_DIR / "flow_mcp_server.py")
SKILL_SRC = BASE_DIR / ".agents" / "skills" / "flow-studio" / "SKILL.md"
PYTHON_EXE = sys.executable


def ensure_dependencies():
    print("[1/4] Verificando dependencias Python (playwright, aiohttp, mcp, pystray, pillow, pywebview)...")
    missing = []
    for mod in ("playwright", "aiohttp", "mcp", "pystray", "PIL", "webview"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"      Instalando pacotes ausentes: {', '.join(missing)}...")
        subprocess.check_call([PYTHON_EXE, "-m", "pip", "install", "-r", str(BASE_DIR / "requirements.txt")])
    else:
        print("      [OK] Todas as bibliotecas ja estao instaladas.")


def merge_mcp_json(file_path: Path):
    """Adiciona ou atualiza a entrada 'flow-studio' em um arquivo mcp_config.json / .mcp.json sem apagar outros MCPs."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            if content:
                data = json.loads(content)
        except Exception:
            data = {}

    if not isinstance(data, dict):
        data = {}
    mcp_servers = data.setdefault("mcpServers", {})
    mcp_servers["flow-studio"] = {
        "command": PYTHON_EXE,
        "args": [MCP_SERVER_SCRIPT],
    }
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"      [OK] MCP registrado em: {file_path}")


def configure_all_agents():
    print("[2/4] Registrando servidor MCP 'flow-studio' nos agentes de IA...")
    home = Path.home()

    # 1. Antigravity (Global)
    merge_mcp_json(home / ".gemini" / "config" / "mcp_config.json")
    merge_mcp_json(home / ".gemini" / "antigravity" / "mcp_config.json")

    # 2. Claude Code / Repo-level .mcp.json
    merge_mcp_json(BASE_DIR / ".mcp.json")
    claude_global = home / ".claude.json"
    if claude_global.exists():
        merge_mcp_json(claude_global)

    # 3. Cursor (Global & Local)
    merge_mcp_json(home / ".cursor" / "mcp.json")
    merge_mcp_json(BASE_DIR / ".cursor" / "mcp.json")

    print("[3/4] Instalando Skill Global 'flow-studio' (com protocolo Auto-Healing)...")
    if SKILL_SRC.exists():
        for dest_dir in (
            home / ".gemini" / "config" / "skills" / "flow-studio",
            home / ".gemini" / "antigravity" / "skills" / "flow-studio",
            home / ".claude" / "skills" / "flow-studio",
        ):
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SKILL_SRC, dest_dir / "SKILL.md")
            print(f"      [OK] Skill instalada em: {dest_dir / 'SKILL.md'}")


def check_chrome_and_login():
    print("[4/4] Verificando Google Chrome e status de login inicial...")
    sys.path.insert(0, str(BASE_DIR))
    import flowapi

    try:
        chrome_path = flowapi.detectar_executavel_chrome()
        print(f"      [OK] Google Chrome detectado: {chrome_path}")
    except Exception as e:
        print(f"      [!] Aviso: {e}")
        return

    print(f"      [OK] Diretorio de perfil isolado: {flowapi.CHROME_PROFILE_DIR}")
    if flowapi.ja_fez_login_inicial():
        print("      [OK] Login inicial ja consta como concluido (.login_completed). O navegador operara 100% invisivel!")
    else:
        print("      [i] Primeiro uso detectado: Na primeira execucao (ou chamando flow_login_browser),")
        print("          o Chrome abrira visivel para voce logar no Google Flow uma unica vez.")


if __name__ == "__main__":
    print("=" * 65)
    print("  INSTALADOR UNIVERSAL - FLOW STUDIO MCP + AUTO-HEALING")
    print("=" * 65)
    ensure_dependencies()
    configure_all_agents()
    check_chrome_and_login()
    print("\n[SUCESSO] Configuracao concluida! O Flow Studio MCP esta pronto para uso.")

