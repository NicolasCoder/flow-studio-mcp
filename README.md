# 🎬 Flow Studio MCP — Google Flow (Veo 3.1 & Nano Banana) AI Server

<p align="center">
  <img src="https://img.shields.io/badge/MCP-Model%20Context%20Protocol-6366f1?style=for-the-badge" alt="MCP"/>
  <img src="https://img.shields.io/badge/Google%20Flow-Veo%203.1%20%26%20Nano%20Banana%202.1-10b981?style=for-the-badge" alt="Google Flow"/>
  <img src="https://img.shields.io/badge/Auto--Healing-DOM%20%2B%20Network%20RPC-f59e0b?style=for-the-badge" alt="Auto-Healing"/>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0ea5e9?style=for-the-badge" alt="Platform"/>
</p>

> **Transforme o [Google Flow](https://flow.google.com/) em um Servidor MCP + Skill + Central de Fila Multi-Projeto com System Tray Flyout e Auto-Healing nativo.**  
> Compatível com **Google Antigravity**, **Claude Code**, **Cursor**, **Windsurf** e **OpenAI Codex / GPT Agents**.

---

## 🌟 Sobre o Projeto

O **Flow Studio MCP** permite que qualquer agente de Inteligência Artificial (ou você mesmo, através de um popup estilo **Apple Control Center** na bandeja do sistema) gere vídeos (**Veo 3.1 Lite / Lower Priority / Fast / Quality / Omni 1.1 Flash**) e imagens (**Nano Banana 2.1 / Pro / Lite**) diretamente na sua conta do Google Flow — **100% em segundo plano (invisível e sem ícone na barra de tarefas)** e com máxima pontuação de confiança no Google reCAPTCHA Enterprise.

### ✨ Principais Diferenciais

- **⚡ Fila Central Única Multi-Projeto (`porta 9334`)**:
  Trabalhando em 2 ou 3 projetos diferentes ao mesmo tempo? Todos os seus agentes MCP enviam os pedidos para um único **Daemon Central (`flow_queue_daemon.py`)** com fila de prioridade persistente (SQLite). Cada vídeo ou imagem gerada é salva automaticamente na pasta exata do projeto que fez o pedido.
- **👻 Modo 100% Invisível (`Off-Screen` + Zero Ícone na Taskbar)**:
  Usa o **Google Chrome oficial** instalado na sua máquina em um perfil exclusivo (`C:\flow-mcp-profile` ou `~/.flow-studio-profile` na porta `9333`), **sem nunca fechar ou tocar no seu Chrome pessoal**. Após o login inicial, tanto a janela quanto o ícone da barra de tarefas ficam invisíveis (`ITaskbarList::DeleteTab`), operando fora da tela (`X = -2400, Y = 0`) sem perder pontuação no reCAPTCHA Enterprise.
- **🍏 System Tray Flyout (Estilo Apple Control Center / Glassmorphism)**:
  Um ícone inteligente fica ao lado do relógio do sistema mostrando o status em tempo real (**Verde** = Pronto, **Âmbar** = Renderizando, **Vermelho** = Aguardando Login). Ao clicar nele, abre-se um popup flutuante com cantos arredondados nativos para:
  - Acompanhar toda a fila dos seus MCPs ao vivo e **definir qual projeto tem prioridade máxima**;
  - Adicionar prompts avulsos com suporte a **Ingredientes** e **Frames IN/OUT**;
  - Subir um arquivo **`.TXT` com dezenas de prompts** e disparar um lote inteiro com a mesma configuração (ex.: 40 imagens `16:9` no `Nano Banana 2.1`);
  - Mostrar/Esconder o navegador na tela com 1 clique.
- **🩹 Auto-Healing Nativo (Auto-Reparo por IA)**:
  Se o Google Flow atualizar o site (mudar o texto de um botão, um seletor CSS ou um código `rpcid` do `batchexecute`), o sistema coleta automaticamente um pacote de diagnóstico contendo **Screenshot + Árvore do DOM + Sniffer de Rede** (`flow_diagnose`) e permite que a própria IA atualize o [`selectors.json`](./selectors.json) a quente (`flow_update_selectors`) sem precisar editar código manualmente.

---

## 🚀 Instalação em 1 Passo (Configuração Automática por IA)

Você não precisa configurar arquivos JSON manualmente. Basta clonar este repositório, abrir a pasta no seu agente de IA (**Antigravity, Claude Code, Cursor, etc.**) e enviar o prompt abaixo:

```text
Acabei de clonar o projeto flow-studio-mcp. Leia o README.md (e CLAUDE.md / AGENTS.md), execute `python setup_mcp.py` para instalar as dependências e registrar o MCP e a Skill no meu computador, inicie o painel `flow_tray.py` e execute `flow_login_browser` caso eu ainda não tenha feito o primeiro login no Google Flow.
```

### Instalação Manual Rápida (Opcional)
```bash
git clone https://github.com/NicolasCoder/flow-studio-mcp.git
cd flow-studio-mcp
python setup_mcp.py
```
Para abrir o ícone na bandeja do sistema (System Tray Flyout), basta dar dois cliques em **[`abrir_dashboard.bat`](./abrir_dashboard.bat)** (ou rodar `pythonw flow_tray.py`).

---

## 🔐 Primeiro Login e Comandos Rápidos de Visibilidade

1. **Primeiro Uso**:
   - Na primeira execução, uma janela limpa do Google Chrome abrirá na sua tela em `https://flow.google.com/`.
   - Faça login na sua conta Google e entre no Google Flow.
   - Assim que o login é detectado, o sistema grava o marcador `.login_completed` e passa a operar **100% invisível** (sem janela na tela e sem ícone na barra de tarefas).
2. **Comandos Rápidos (via Chat da IA ou pelo Painel Tray)**:
   - **`/showbrowser`** (`flow_show_browser`): Traz imediatamente o navegador para a tela (`X = 100, Y = 80`) e restaura o ícone na barra de tarefas para você assistir à geração ao vivo.
   - **`/hidebrowser`** (`flow_hide_browser`): Esconde imediatamente o navegador de volta para fora da tela (`X = -2400, Y = 0`) e remove o ícone da barra de tarefas sem interromper a renderização.
   - **`/loginbrowser`** (`flow_login_browser`): Abre o navegador visível caso queira trocar de conta Google.

---

## 🎨 Modelos e Recursos Suportados

### 🎬 Modelos de Vídeo (`tipo="video"`)
| Alias no MCP / Painel | Nome no Google Flow | Indicação |
| :--- | :--- | :--- |
| `"lower_priority"` | `Veo 3.1 - Lite [Lower Priority]` | **Padrão** — Mais econômico para testes e grandes filas |
| `"lite"` | `Veo 3.1 - Lite` | Rápido e leve em prioridade normal |
| `"fast"` | `Veo 3.1 - Fast` | Geração rápida com alta fidelidade de movimento |
| `"quality"` | `Veo 3.1 - Quality` | Qualidade máxima cinematográfica |
| `"omni"` | `Omni 1.1 Flash` | Modelo alternativo ultrarrápido |

### 🖼️ Modelos de Imagem (`tipo="imagem"`)
| Alias no MCP / Painel | Nome no Google Flow | Indicação |
| :--- | :--- | :--- |
| `"2.1"` | `Nano Banana 2.1` | **Padrão** — Excelente qualidade e consistência |
| `"pro"` | `Nano Banana Pro` | Máximo detalhamento fotográfico |
| `"lite"` | `Nano Banana 2 Lite` | Geração instantânea |

### ⚙️ Parâmetros Avançados (`flow_generate` & `flow_generate_batch`)
- **Proporções (`proporcao`)**: `"16:9"`, `"9:16"`, `"4:3"`, `"1:1"`, `"3:4"`
- **Durações de Vídeo (`duracao`)**: `"4s"`, `"6s"`, `"8s"`, `"10s"`
- **Resoluções de Vídeo (`resolucao`)**: `"720p"`, `"360p"`
- **Ingredientes (`ingredientes`)**: Lista de imagens locais (`["personagem.png", "objeto.png"]`) anexadas ao prompt para manter consistência de personagens, produtos ou cenários.
- **Frames Inicial e Final (`frame_in`, `frame_out`, `swap_frames`)**: Defina a imagem exata de início (`Start`) e/ou fim (`End`) do vídeo gerado.
- **Prioridade na Fila (`priority`)**: `10` (Alta Prioridade — fura a fila), `100` (Normal), `200` (Baixa / Background).

---

## 🛠️ Ferramentas MCP Disponíveis para o Agente de IA

| Ferramenta MCP | Descrição |
| :--- | :--- |
| `flow_generate` | Gera um vídeo ou imagem na Fila Central Única e retorna o caminho final do arquivo baixado + `job_id`. |
| `flow_generate_batch` | Enfileira uma lista de múltiplos vídeos/imagens de uma só vez na Fila Central Única. |
| `flow_queue_status` | Consulta o status de um `job_id` específico ou lista todos os jobs e projetos na fila global. |
| `flow_show_browser` | Traz o navegador invisível para a tela (`X = 100, Y = 80`). |
| `flow_hide_browser` | Oculta o navegador fora da tela (`X = -2400, Y = 0`) e remove seu ícone da barra de tarefas. |
| `flow_login_browser` | Abre o navegador visível para login inicial ou troca de conta no Google Flow. |
| `flow_new_project` | Cria um projeto limpo no Google Flow. |
| `flow_diagnose` | **(Auto-Healing)** Coleta Screenshot + Botões/Inputs do DOM + RPCs `batchexecute` da página atual. |
| `flow_update_selectors` | **(Auto-Healing)** Atualiza seletores CSS, textos de modelos ou `rpcids` em `selectors.json` a quente. |
| `flow_reload_daemon` | **(Auto-Healing)** Recarrega `flowapi.py` e `selectors.json` no Daemon sem derrubar a fila. |

---

## 🩹 Protocolo Auto-Healing (Como o Auto-Reparo Funciona)

Caso o Google atualize a interface do Flow no futuro:
1. Qualquer erro em `flow_generate` gera automaticamente um snapshot completo em `diagnostics/last_diagnostic_report.json` e `diagnostics/last_diagnostic_screenshot.png`.
2. Peça ao seu agente de IA:
   > *"A geração no Flow falhou. Use `flow_diagnose` para inspecionar o DOM e as chamadas de rede atuais do Google Flow e aplique o auto-reparo com `flow_update_selectors`."*
3. O agente compara os seletores antigos com os botões reais da página, atualiza o [`selectors.json`](./selectors.json) e retoma a geração imediatamente.

---

## 📁 Estrutura do Repositório

```text
flow-studio-mcp/
├── README.md                  # Documentação completa do projeto
├── abrir_dashboard.bat        # Atalho para iniciar o System Tray Flyout sem janela de terminal
├── flow_tray.py               # System Tray + Flyout Popup estilo Apple Control Center
├── setup_mcp.py               # Instalador universal (Antigravity, Claude Code, Cursor, etc.)
├── flow_mcp_server.py         # Servidor FastMCP com ferramentas de geração, fila e Auto-Healing
├── flow_queue_daemon.py       # Daemon HTTP (porta 9334) de fila única com prioridade por projeto
├── flowapi.py                 # Motor Playwright (porta 9333) + Modo Invisível & Ocultação Taskbar
├── selectors.json             # Seletores CSS, RPC IDs e Modelos (Hot-Reload para Auto-Healing)
├── config.json                # Configurações padrão de geração
├── requirements.txt           # Dependências Python (playwright, aiohttp, mcp, pystray, pillow, pywebview)
├── CLAUDE.md                  # Instruções nativas para o Claude Code
├── AGENTS.md                  # Instruções nativas para OpenAI Codex / GPT / Cursor
└── .agents/
    └── skills/
        └── flow-studio/
            └── SKILL.md       # Skill oficial para o Google Antigravity
```
