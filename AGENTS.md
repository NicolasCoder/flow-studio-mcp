# AGENTS.md — Flow Studio MCP (Instructions for OpenAI Codex / GPT / Cursor / Windsurf Agents)

Este arquivo fornece contexto completo para qualquer Agente de IA (**GPT / Codex, Cursor, Windsurf, Claude Code, Antigravity**) configurar, operar e **auto-reparar (Auto-Heal)** o **Flow Studio MCP**.

## 1. Setup Automático para o Usuário

Quando o usuário pedir para instalar ou configurar este repositório:
1. Execute `python setup_mcp.py`. O script instala `playwright`, `aiohttp` e `mcp` e registra automaticamente o servidor MCP `flow-studio` nos arquivos de configuração globais e locais da máquina do usuário.
2. Inicie o login único chamando a tool MCP `flow_login_browser` (ou via terminal: `python -c "import asyncio, flow_mcp_server; print(asyncio.run(flow_mcp_server.flow_login_browser()))"`).
3. Após o usuário fazer login no Google Flow na janela aberta, chame `flow_hide_browser` para ocultar a janela fora da tela (`X=-2400, Y=0`).

## 2. Como Usar as Tools do MCP `flow-studio`

- `flow_generate`: Gera vídeo (`tipo="video"`) ou imagem (`tipo="imagem"`) na fila central única (`127.0.0.1:9334`) e salva em `output_path`, retornando `job_id`, `media_id` e `file_path`.
  - Suporta `modelo` (`"lower_priority"`, `"lite"`, `"fast"`, `"quality"`, `"omni"`, `"2.1"`, `"pro"`), `proporcao` (`"16:9"`, `"9:16"`, `"4:3"`, `"1:1"`, `"3:4"`), `duracao` (`"4s"`, `"6s"`, `"8s"`, `"10s"`), `resolucao` (`"720p"`, `"360p"`), `frame_in`, `frame_out`, `swap_frames` e `ingredientes`.
- `flow_generate_batch`: Enfileira múltiplos itens de uma só vez.
- `flow_queue_status`: Consulta a fila global compartilhada entre projetos.
- `flow_show_browser` / `flow_hide_browser` / `flow_login_browser`: Controla a visibilidade da janela do Chrome em tempo real.

## 3. Auto-Healing (Como o Agente se Auto-Conserta se o Google Flow mudar)

Se uma geração falhar por mudança na interface ou API interna do Google Flow:
1. Chame `flow_diagnose(open_settings_menu=True, take_screenshot=True)`.
2. Inspecione o arquivo de imagem gerado em `diagnostics/last_diagnostic_screenshot.png` e o JSON em `diagnostics/last_diagnostic_report.json` (contém todos os botões visíveis no DOM, `aria-label`s e os últimos `rpcids` de rede `batchexecute`).
3. Atualize o seletor ou RPC ID correspondente em `selectors.json` usando a tool `flow_update_selectors` (ou edite `flowapi.py` e chame `flow_reload_daemon`).
4. Respeite sempre a arquitetura híbrida anti-reCAPTCHA: preenchimento de `.ProseMirror` + clique real no botão de envio + interceptação da resposta com `page.expect_response`, mantendo a janela do Chrome com `windowState: "normal"` em `X=-2400, Y=0`.

