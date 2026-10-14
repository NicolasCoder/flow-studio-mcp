---
name: flow-studio
description: Gera vídeos (Veo 3.1 / Omni 1.1) e imagens (Nano Banana 2.1 / Pro / Lite) no Google Flow usando uma Fila Central Única compartilhada entre múltiplos projetos, com suporte a Ingredientes (ING), Frames Inicial/Final (IN/OUT), modo invisível off-screen, comandos de visibilidade (/showbrowser, /hidebrowser, /loginbrowser) e protocolo completo de Auto-Healing.
---

# Flow Studio (MCP + Fila Central Única + Auto-Healing)

Esta skill instrui o agente de IA a operar, instalar e **auto-reparar (Auto-Heal)** o ecossistema **Flow Studio** para geração de vídeos e imagens no Google Flow (`https://flow.google.com/`).

---

## 1. Instalação Zero-Toque (Caso o usuário acabe de clonar o repositório)

Se o usuário pedir para instalar ou configurar o projeto pela primeira vez:
1. Execute `python setup_mcp.py` na pasta do repositório `flow-studio-mcp`. Ele instala dependências e registra automaticamente o MCP e a Skill no Antigravity, Claude Code e Cursor usando os caminhos reais do computador do usuário.
2. Em seguida, chame a ferramenta `flow_login_browser` para abrir a janela do Google Chrome isolado (`porta 9333`) visível na tela e peça para o usuário fazer login na conta Google uma única vez.
3. Assim que o usuário confirmar que fez login, chame `flow_hide_browser` para mover o navegador para fora da tela (`X = -2400, Y = 0`).

---

## 2. Ferramentas do MCP (`flow-studio`)

- **`flow_generate`**: Gera 1 vídeo ou imagem na fila central única e baixa automaticamente no `output_path`.
  - `prompt` (str): Descrição detalhada da cena/imagem.
  - `tipo` (str): `"video"` ou `"imagem"`.
  - `output_path` (str): Caminho completo do arquivo (`.mp4` / `.png`) ou pasta de destino.
  - `modelo` (str):
    - Vídeo: `"lower_priority"` (`Veo 3.1 - Lite [Lower Priority]`), `"lite"` (`Veo 3.1 - Lite`), `"fast"` (`Veo 3.1 - Fast`), `"quality"` (`Veo 3.1 - Quality`), `"omni"` (`Omni 1.1 Flash`).
    - Imagem: `"2.1"` (`Nano Banana 2.1`), `"pro"` (`Nano Banana Pro`), `"lite"` (`Nano Banana 2 Lite`).
  - `proporcao` (str): `"16:9"`, `"9:16"`, `"4:3"`, `"1:1"`, `"3:4"`.
  - `duracao` (str): `"4s"`, `"6s"`, `"8s"`, `"10s"` (apenas vídeo).
  - `resolucao` (str): `"720p"`, `"360p"` (apenas vídeo).
  - `quantidade` (str): `"x1"`, `"x2"`, `"x3"`, `"x4"`.
  - `frame_in` (str): Caminho local da imagem de primeiro frame (`Start`).
  - `frame_out` (str): Caminho local da imagem de último frame (`End`).
  - `swap_frames` (bool): Inverte os frames IN e OUT.
  - `ingredientes` (list[str] | str): Caminhos locais de imagens de referência (`ING`).
- **`flow_generate_batch`**: Enfileira múltiplos vídeos/imagens de uma só vez na fila central.
- **`flow_queue_status`**: Consulta toda a fila global (compartilhada entre múltiplos projetos) ou acompanha um `job_id`.
- **`flow_show_browser` / `flow_hide_browser` / `flow_login_browser`**: Mostra (`X=100, Y=80`), esconde (`X=-2400, Y=0`) ou abre o Chrome isolado para login.
- **`flow_diagnose` / `flow_update_selectors` / `flow_reload_daemon`**: Ferramentas de **Auto-Healing** em tempo real.

---

## 3. Protocolo de Auto-Healing (Auto-Reparo pelo Agente de IA)

Se o Google Flow atualizar sua interface (mudar nomes de botões, `aria-label`, classes CSS, estrutura de cards `<flow-video-tile>` / `<flow-image-tile>`, IDs de RPC `batchexecute` ou regras de reCAPTCHA), **você (Agente de IA) DEVE diagnosticar e consertar o projeto autonomamente** seguindo este roteiro:

### Passo 1: Inspecionar a falha e o DOM ao vivo
1. Quando `flow_generate` falha, ele já retorna um objeto `diagnostics` com `report_path`, `screenshot_path`, `recent_rpcs` e `alerts_or_toasts`.
2. Chame a ferramenta MCP **`flow_diagnose(open_settings_menu=True, take_screenshot=True)`**.
3. Leia os dados retornados por `flow_diagnose` e visualize a imagem `diagnostics/last_diagnostic_screenshot.png` para ver exatamente o que está na tela do Flow.

### Passo 2: Identificar o que mudou no Google Flow
Verifique as 4 causas clássicas de mudança no Flow:
1. **Mudança de Seletor de Botão / Menu (`selectors.json` -> `selectors`)**:
   - Compare os seletores atuais em `selectors.json` com a lista `dom_snapshot.buttons` e `dom_snapshot.editors` retornada por `flow_diagnose`.
   - Exemplo: se o botão de disparar geração mudou de `[aria-label="Start generation"]` para outro `aria-label` ou ícone, atualize `start_generation_btn`.
   - **Importante**: Ao trocar de modo (`Image`/`Video` ou `Ingredients`/`Frames`), sempre limpe os chips de ingredientes anteriores (`limpar_barra_prompt`) antes de abrir o menu de configurações, pois ingredientes presos na barra travam a troca de aba no Flow.
2. **Mudança de ID de RPC `batchexecute` (`selectors.json` -> `rpc_ids`)**:
   - Atualmente o Flow usa:
     - `YhhmEf` (Text-to-Video e Ingredients-to-Video)
     - `eb1hJf` (Frames IN/OUT Image-to-Video)
     - `ogiZ0b` (Geração de Imagem)
     - `jwpduf` (Polling de status de renderização)
   - Olhe `recent_network_rpcs` no retorno de `flow_diagnose` para ver quais `rpcids=...` o navegador disparou quando o botão de gerar foi clicado. Se surgiu um novo código de 6 caracteres, adicione-o em `selectors.json -> rpc_ids`.
3. **Regras Anti-Bloqueio reCAPTCHA Enterprise (NUNCA violar!)**:
   - **NUNCA** dispare geração de vídeo/imagem via `fetch()` puro dentro de `page.evaluate` chamando `grecaptcha.enterprise.execute` manualmente — o Google bloqueia com `PUBLIC_ERROR_UNUSUAL_ACTIVITY` (`400`/`403`) por falta de telemetria comportamental de UI.
   - **SEMPRE** preencha o prompt no editor `.ProseMirror` via Playwright e clique fisicamente no botão de gerar (`gen_btn.click()`) interceptando a resposta de rede com `page.expect_response(...)`.
   - **NUNCA** use `--headless` nem minimize a janela (`windowState: "minimized"`). Mantenha sempre `windowState: "normal"` posicionada fora da tela (`left: -2400, top: 0`).
4. **Multi-Conta Google (`WIZ_global_data.Im6cmf`) e Download de Mídia**:
   - Quando o usuário tem mais de uma conta Google logada, a URL base muda para `/u/1/_/AiSandboxAngularFrontend`. Sempre extraia `window.WIZ_global_data.Im6cmf` em `obter_parametros_pagina`.
   - Os vídeos nos cards `<flow-video-tile>` só injetam a tag `<video src="...">` quando recebem `hover(force=True)`. Além disso, as URLs podem vir de `flow-content.google` ou `flow.google.com/asb/...`. Sempre baixe usando `await page.context.request.get(url)` para incluir os cookies autenticados da sessão.

### Passo 3: Aplicar a correção em tempo real (Sem derrubar a fila)
- Se a mudança for apenas de seletor CSS, `rpc_ids` ou nome de modelo:
  - Chame **`flow_update_selectors({"selectors": {"nome_do_seletor": "novo_seletor"}})`**. A alteração entra em vigor instantaneamente!
- Se precisar ajustar alguma lógica Python em `flowapi.py`:
  - Edite `flowapi.py` e em seguida chame **`flow_reload_daemon()`** para recarregar o módulo em memória no daemon central.
- Reexecute `flow_generate` imediatamente para validar que o Auto-Healing funcionou!

