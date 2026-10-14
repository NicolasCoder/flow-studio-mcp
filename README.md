# 🎬 Flow Studio MCP — Automação Google Flow (Veo 3.1 & Nano Banana) com Fila Central Única e Auto-Healing

Transforme o **Google Flow** (`https://flow.google.com/`) em um **Servidor MCP + Skill** pronto para qualquer agente de IA (**Google Antigravity, Claude Code, Cursor, Windsurf, OpenAI Codex / GPT**).

Gere vídeos (**Veo 3.1 Lite / Lower Priority / Fast / Quality / Omni 1.1 Flash**) e imagens (**Nano Banana 2.1 / Pro / Lite**) com suporte completo a **Ingredientes (Personagens/Objetos)** e **Frames Inicial/Final (IN/OUT)**, operando **100% invisível fora da tela** sem risco de bloqueio por reCAPTCHA Enterprise.

---

## ✨ Principais Diferenciais

1. **⚡ Fila Central Única Multi-Projeto (`porta 9334`)**:
   - Trabalhando em 2 ou 3 projetos diferentes ao mesmo tempo? Sem problema! Todos os agentes enviam seus pedidos para o mesmo **Daemon Central (`flow_queue_daemon.py`)**, que organiza tudo em uma única fila global com persistência SQLite e salva cada vídeo/imagem na pasta exata do projeto que pediu.
2. **👻 Modo Invisível Real (`Off-Screen`) & Perfil Isolado (`porta 9333`)**:
   - Usa o **Google Chrome normal** da sua máquina (Windows, macOS ou Linux) em um perfil exclusivo (`~/.flow-studio-profile`), **sem nunca fechar ou interferir no seu Chrome pessoal**.
   - Após o primeiro login, a janela opera posicionada fora da tela (`X = -2400, Y = 0`) com `windowState = "normal"`, mantendo pontuação máxima no Google reCAPTCHA Enterprise sem aparecer no seu monitor.
3. **🩹 Auto-Healing Nativo (Auto-Reparo por IA)**:
   - Se o Google Flow mudar o nome de um botão, um seletor CSS ou um ID de requisição interna (`batchexecute`), o próprio agente de IA recebe um pacote de diagnóstico com **Screenshot da tela + Árvore de Botões do DOM + Sniffer de RPCs de rede** (`flow_diagnose`) e atualiza o arquivo [`selectors.json`](./selectors.json) em tempo real (`flow_update_selectors`), consertando a automação sozinho!
4. **🤖 Compatível com Todos os Agentes**:
   - Inclui configuração automática e arquivos de instrução nativos para **Antigravity** ([`.agents/skills/flow-studio/SKILL.md`](./.agents/skills/flow-studio/SKILL.md)), **Claude Code** ([`CLAUDE.md`](./CLAUDE.md)), **Cursor** (`.cursor/mcp.json`) e **GPT / Codex** ([`AGENTS.md`](./AGENTS.md)).

---

## 🚀 Instalação em 1 Passo (Deixe a sua IA configurar tudo!)

Você não precisa configurar arquivos JSON na mão. Basta clonar esta pasta, abrir no seu agente de IA (**Antigravity, Claude Code, Cursor, etc.**) e colar o seguinte prompt:

> **📋 Copie e cole para a sua IA:**
> ```text
> Acabei de baixar o projeto flow-studio-mcp. Leia o README.md (e CLAUDE.md / AGENTS.md), execute o script `python setup_mcp.py` para instalar as dependências e registrar o MCP e a Skill no meu computador, e em seguida execute `flow_login_browser` para abrir o navegador isolado e eu fazer meu primeiro login no Google Flow.
> ```

### O que o `python setup_mcp.py` faz automaticamente?
1. Verifica e instala as bibliotecas necessárias (`playwright`, `aiohttp`, `mcp`).
2. Detecta o caminho exato do Python e do Google Chrome no seu computador (Windows, Mac ou Linux).
3. Registra o servidor MCP `flow-studio` automaticamente no **Antigravity**, **Claude Code**, **Cursor** e instala a Skill global.

---

## 🔐 Como funciona o Primeiro Login e os Comandos de Visibilidade

1. **Primeiro Uso**:
   - Na primeira vez que rodar, uma janela limpa do Google Chrome será aberta na sua tela em `https://flow.google.com/`.
   - Faça o login na sua conta Google e entre no Flow.
   - Assim que terminar, avise a IA (ou feche a janela). O sistema criará o marcador `.login_completed` e moverá o navegador para o **modo invisível fora da tela (`X = -2400, Y = 0`)**.
2. **Comandos Rápidos no Chat da IA**:
   - **`/showbrowser`** (`flow_show_browser`): Traz imediatamente o navegador invisível para a sua tela (`X = 100, Y = 80`) para você assistir ao processo em tempo real.
   - **`/hidebrowser`** (`flow_hide_browser`): Esconde imediatamente o navegador de volta para fora da tela (`X = -2400, Y = 0`) sem interromper nenhuma renderização.
   - **`/loginbrowser`** (`flow_login_browser`): Abre o navegador visível caso você queira trocar de conta Google no futuro.

---

## 🎨 Modelos e Recursos Suportados

Quando pedir para a sua IA gerar mídias pelo MCP (`flow_generate` ou `flow_generate_batch`), você pode especificar qualquer combinação abaixo:

### Modelos de Vídeo (`tipo="video"`)
| Alias no MCP | Nome no Google Flow | Indicação |
| :--- | :--- | :--- |
| `"lower_priority"` | `Veo 3.1 - Lite [Lower Priority]` | **Padrão** — Mais econômico para testes e lotes |
| `"lite"` | `Veo 3.1 - Lite` | Rápido e leve em prioridade normal |
| `"fast"` | `Veo 3.1 - Fast` | Geração rápida com alta fidelidade |
| `"quality"` | `Veo 3.1 - Quality` | Qualidade máxima cinematográfica |
| `"omni"` | `Omni 1.1 Flash` | Modelo alternativo ultrarrápido |

### Modelos de Imagem (`tipo="imagem"`)
| Alias no MCP | Nome no Google Flow | Indicação |
| :--- | :--- | :--- |
| `"2.1"` | `Nano Banana 2.1` | **Padrão** — Excelente qualidade e consistência |
| `"pro"` | `Nano Banana Pro` | Máximo detalhamento fotográfico |
| `"lite"` | `Nano Banana 2 Lite` | Geração instantânea |

### Parâmetros Avançados
- **Proporções (`proporcao`)**: `"16:9"`, `"9:16"`, `"4:3"`, `"1:1"`, `"3:4"`
- **Durações de Vídeo (`duracao`)**: `"4s"`, `"6s"`, `"8s"`, `"10s"`
- **Resoluções de Vídeo (`resolucao`)**: `"720p"`, `"360p"`
- **Quantidade (`quantidade`)**: `"x1"`, `"x2"`, `"x3"`, `"x4"`
- **Ingredientes (`ingredientes`)**: Lista de imagens locais (ex: `["personagem.png", "objeto.png"]`) para manter consistência de personagens, produtos ou estilo visual.
- **Primeiro e Último Frame (`frame_in`, `frame_out`, `swap_frames`)**: Imagens locais para iniciar (`Start`) e/ou terminar (`End`) o vídeo exatamente naquele frame!

---

## 🩹 Como funciona o Auto-Healing (Auto-Reparo)?

Se algum dia o Google atualizar o site do Flow (mudar o texto de um botão, trocar um seletor CSS ou alterar o código interno de uma requisição `batchexecute`), **você não precisa editar código manualmente**:

1. Quando ocorre qualquer falha em `flow_generate`, o Daemon Central captura automaticamente:
   - Um **Screenshot** do estado exato da página (`diagnostics/last_diagnostic_screenshot.png`).
   - Uma lista de todos os **botões, `aria-label`s, inputs e tags `<flow-*>`** visíveis no DOM (`diagnostics/last_diagnostic_report.json`).
   - As últimas chamadas de rede `batchexecute` com seus respectivos `rpcids`.
2. Basta dizer para a sua IA (no Antigravity, Claude Code ou Cursor):
   > *"A geração no Flow deu erro. Use a ferramenta `flow_diagnose` para ver o que mudou na página do Google Flow e faça o auto-reparo."*
3. A IA analisa o diagnóstico, atualiza o [`selectors.json`](./selectors.json) via `flow_update_selectors` (ou ajusta [`flowapi.py`](./flowapi.py) e chama `flow_reload_daemon`) e retoma a fila na mesma hora!

---

## 🍏 Painel System Tray Estilo Apple (Glassmorphism)

O Flow Studio inclui um aplicativo nativo para a bandeja do sistema (**System Tray**, ao lado do relógio do Windows/Mac/Linux):

- **Como abrir**: Execute [`abrir_dashboard.bat`](./abrir_dashboard.bat) ou rode `python flow_tray.py`.
- **Ícone na Bandeja com Status em Tempo Real**:
  - 🟢 **Verde**: Conectado e pronto para receber pedidos.
  - 🟡 **Âmbar**: Renderizando vídeo/imagem ativamente no Flow.
  - 🔴 **Vermelho**: Desconectado ou aguardando primeiro login.
  - *Dica*: Clicar com o botão direito no ícone abre um menu rápido para Mostrar/Esconder o navegador, fazer Login ou Sair.
- **Janela Pop-up Estilo macOS Glassmorphism (Ao clicar no ícone)**:
  - **📊 Fila Central**: Acompanhe o job em execução e todos os itens na fila de espera. Cada item mostra qual projeto solicitou a geração (`PajeAutomation_Amigo`, `Projeto B`, etc.). Você pode clicar em **"⚡ Priorizar Este Projeto"** ou em **"⬆️ Priorizar"** em um job específico para passá-lo para a frente da fila!
  - **➕ Criar**: Envie prompts manualmente pelo painel escolhendo Tipo (Vídeo / Imagem), Modelo, Proporção, Duração, Resolução, Frames Inicial/Final (IN/OUT), Ingredientes e pasta de destino.
  - **📑 Lote TXT**: Cole uma lista com 20, 40 ou 100 prompts (ou suba um arquivo `.txt`) e aplique uma configuração unificada (ex: transformar todos em imagens 16:9 no Nano Banana 2.1) e envie todos para a fila central com 1 clique!
  - **⚙️ Sistema & Navegador**: Veja o status das portas 9333 e 9334, login e use os botões rápidos para Mostrar/Esconder o navegador ou rodar o Diagnóstico de Auto-Healing.

---

## 📁 Estrutura de Arquivos da Pasta

```text
flow-studio-mcp/
├── README.md                  # Este tutorial completo
├── abrir_dashboard.bat        # Inicializador em 1 clique do Painel Tray Glassmorphism
├── flow_tray.py               # Aplicativo System Tray + Pop-up Apple Glassmorphism (pystray + pywebview)
├── setup_mcp.py               # Instalador universal (Antigravity, Claude Code, Cursor, etc.)
├── flow_mcp_server.py         # Servidor MCP com ferramentas de geração, fila e Auto-Healing
├── flow_queue_daemon.py       # Daemon HTTP (porta 9334) de fila única com suporte a prioridade
├── flowapi.py                 # Motor Playwright multiplataforma (porta 9333) + Ocultação Taskbar nativa
├── selectors.json             # Seletores CSS, RPC IDs e Modelos (Hot-Reload para Auto-Healing)
├── config.json                # Configurações padrão de geração
├── requirements.txt           # Dependências Python (playwright, aiohttp, mcp, pystray, pillow, pywebview)
├── CLAUDE.md                  # Instruções de operação e Auto-Healing para o Claude Code
├── AGENTS.md                  # Instruções de operação e Auto-Healing para GPT / Codex / Cursor
└── .agents/
    └── skills/
        └── flow-studio/
            └── SKILL.md       # Skill oficial para Google Antigravity
```


