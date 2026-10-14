# CLAUDE.md — Flow Studio MCP (Instruções para Claude Code / Agentes de IA)

Este repositório contém o **Flow Studio MCP**, um servidor MCP + Daemon de Fila Central Única para geração automatizada de vídeos (**Veo 3.1 / Omni 1.1**) e imagens (**Nano Banana 2.1 / Pro / Lite**) no **Google Flow** (`https://flow.google.com/`), operando 100% invisível fora da tela (off-screen) e com capacidade de **Auto-Healing (Auto-Reparo)**.

## 1. Como Configurar / Instalar para o Usuário

Se o usuário acabou de clonar este repositório e pediu para você configurar tudo:
1. Execute no terminal:
   ```bash
   python setup_mcp.py
   ```
   Isso instalará as dependências (`playwright`, `aiohttp`, `mcp`), detectará o Google Chrome do sistema e criará/atualizará os arquivos `.mcp.json`, `~/.claude.json`, `~/.cursor/mcp.json` e `~/.gemini/config/mcp_config.json` com os caminhos exatos da máquina do usuário.
2. Abra o navegador isolado para o primeiro login do usuário chamando a ferramenta MCP `flow_login_browser` (ou executando `python -c "import asyncio, flow_mcp_server; print(asyncio.run(flow_mcp_server.flow_login_browser()))"`).
3. Peça ao usuário para fazer login na conta Google na janela que se abriu. Assim que ele confirmar, chame `flow_hide_browser` para esconder a janela fora da tela (`X = -2400, Y = 0`).

## 2. Arquitetura do Projeto

- **`flow_mcp_server.py`**: Servidor MCP (`FastMCP("flow-studio")`) com as ferramentas `flow_generate`, `flow_generate_batch`, `flow_queue_status`, `flow_login_browser`, `flow_show_browser`, `flow_hide_browser`, `flow_new_project`, `flow_diagnose`, `flow_update_selectors` e `flow_reload_daemon`.
- **`flow_queue_daemon.py`**: Serviço HTTP local (`http://127.0.0.1:9334`) que mantém **uma única fila global** (`asyncio.Queue` + SQLite `flow_queue.db`). Se o usuário estiver com vários projetos abertos simultaneamente, todas as instâncias MCP enviam os trabalhos para a porta `9334` sem colisão.
- **`flowapi.py`**: Motor Playwright que controla o Google Chrome isolado na porta `9333` (`~/.flow-studio-profile` ou `C:\flow-mcp-profile`).
- **`selectors.json`**: Arquivo JSON recarregado dinamicamente em tempo real contendo todos os seletores DOM, IDs de RPC (`YhhmEf`, `eb1hJf`, `ogiZ0b`, `jwpduf`) e nomes de modelos.

## 3. Protocolo de Auto-Healing (Auto-Reparo quando o Google Flow mudar)

Se qualquer geração falhar ou se o Google Flow atualizar seletores, menus, botões ou RPCs:
1. **Execute o Diagnóstico**: Chame a ferramenta MCP `flow_diagnose(open_settings_menu=True, take_screenshot=True)`.
2. **Analise o Relatório e o Screenshot**:
   - Verifique `diagnostics/last_diagnostic_screenshot.png` (use sua ferramenta de leitura de imagem para ver a tela atual do Flow).
   - Compare os botões visíveis em `dom_snapshot.buttons` e os RPCs capturados em `recent_network_rpcs` com o que está configurado em `selectors.json`.
3. **Regras Críticas do Google Flow (Não quebrar!)**:
   - **Anti-reCAPTCHA Block (`PUBLIC_ERROR_UNUSUAL_ACTIVITY`)**: Nunca envie o prompt de geração por `fetch()` direto via JS. Sempre preencha `.ProseMirror` e clique no botão de enviar via Playwright enquanto intercepta a resposta `batchexecute` com `page.expect_response`.
   - **Modo Invisível Off-Screen**: Nunca use `--headless` nem minimize a janela (`windowState: "minimized"`), pois isso reduz o score do reCAPTCHA Enterprise e pausa a renderização de `<flow-video-tile>`. Use sempre `windowState: "normal"` com `left: -2400, top: 0`.
   - **Limpeza de Ingredientes**: Sempre execute `limpar_barra_prompt(page)` antes de abrir o menu de configurações (`Settings trigger`), pois chips de ingredientes anteriores impedem a troca entre `Image`/`Video` ou `Frames`/`Ingredients`.
   - **Hover em Vídeos**: O elemento `<video src="...">` dentro de `flow-video-tile` é lazy-loaded e só aparece no DOM após `tile.hover(force=True)`.
4. **Aplique o Reparo Quente (Hot-Fix)**:
   - Se um seletor ou RPC mudou, atualize `selectors.json` usando `flow_update_selectors(...)`.
   - Se editou `flowapi.py`, chame `flow_reload_daemon()` para recarregar o código no daemon sem reiniciar a fila.
   - Reexecute o job imediatamente!

