# Periscope

**Phone-friendly, local-first access to Jan models, with opt-in chat imports.**

Periscope is a small companion project for [Jan](https://jan.ai/) and [Open WebUI](https://docs.openwebui.com/).

- **Jan runs the models** on your existing workstation. Nothing gets downloaded twice.
- **Open WebUI provides the interface** for a phone or desktop browser and stores its own conversations on the workstation.
- **Periscope's bridge** reads only explicitly linked Jan Desktop threads and imports copies of them into Open WebUI. Other Jan threads are not touched.

> **Sync status:** The first release is **selective one-way import**, NOT live two-way synchronization. Chats you continue in Open WebUI remain there; they do **not** appear in Jan Desktop. Periscope deliberately does not modify Jan's files. Importing a thread creates one Open WebUI conversation and records a mapping; it does not reconcile later edits. Never assume a chat is live-linked until a later release explicitly implements that.

## Architecture

```
Phone/browser -> Open WebUI (localhost:3000) -> Jan's OpenAI-compatible API (localhost:1337)
                       |
                  Open WebUI DB
                       ^
                selected chat import
                       |
     Periscope -> Jan Desktop thread.json + messages.jsonl (read-only)
```

Open WebUI is the **front end**, not a second model server. Periscope is a selective import tool, not a proxy for prompts.

## Getting started (Build-Arch / Linux)

Prerequisites: Jan Desktop running with its local API enabled, `uv` installed, a browser, and a local Jan model. Docker is **not** required.

1. Clone the repository:

   ```bash
   git clone https://github.com/andr8076/Periscope.git
   cd Periscope
   ```

2. Verify that Jan responds. It normally listens only on loopback:

   ```bash
   curl -f http://127.0.0.1:1337/v1/models
   ```

3. Start the browser interface in a terminal:

   ```bash
   ./scripts/start-webui.sh
   ```

   The first run downloads Open WebUI into uv's managed cache. Open `http://127.0.0.1:3000` and create the **first admin account**. This is your local Open WebUI account, not a Jan account. Afterward, disable additional signups in Open WebUI's admin settings. Chats live in `~/.local/share/periscope/open-webui/`, not in the uv cache. Close the terminal or press Ctrl+C to stop the interface. Nothing is installed as a startup service.

4. In Open WebUI, select a model returned by Jan. The launcher preconfigures the OpenAI-compatible connection to `http://127.0.0.1:1337/v1` and disables Ollama. If your Open WebUI installation already has saved connections, use **Admin Settings -> Connections** to check the Jan connection.

5. Optionally install the tiny command-line bridge (Python 3.10+; no third-party dependencies):

   ```bash
   uv run --python 3.12 --project . periscope doctor
   uv run --python 3.12 --project . periscope list
   ```

## Link only selected Jan Desktop conversations

```bash
uv run --python 3.12 --project . periscope list
uv run --python 3.12 --project . periscope link <JAN_THREAD_ID>
uv run --python 3.12 --project . periscope status
uv run --python 3.12 --project . periscope export ./jan-selected-openwebui.json
```

`export` produces the [official Open WebUI chat import format](https://docs.openwebui.com/features/chat-conversations/data-controls/import-export/). In Open WebUI, open **Settings -> Data Controls -> Import Chats** and select the JSON. This works without an API token.

Alternatively, create an Open WebUI API token from your Open WebUI account settings and import automatically:

```bash
export PERISCOPE_WEBUI_TOKEN='your-local-webui-api-token'
uv run --python 3.12 --project . periscope push
```

`push` calls Open WebUI's authenticated chat import API and records the returned chat ID in Periscope's link registry. **It skips already imported threads**, rather than importing duplicates on a normal second run. The API token must not be committed or saved in the repository. A failed push never changes Jan's files.

`periscope unlink <JAN_THREAD_ID>` stops tracking a Jan thread; it **does not delete** the conversation imported into Open WebUI.

### State and configuration

- Jan source: `PERISCOPE_JAN_DATA` overrides auto-detection of `~/.local/share/Jan-nightly/data` and `~/.local/share/Jan/data`.
- Periscope registry: `~/.local/share/periscope/links.json` (override with `PERISCOPE_STATE_DIR`). Keep this private.
- Open WebUI data: `~/.local/share/periscope/open-webui/`.
- Open WebUI URL: `PERISCOPE_WEBUI_URL` defaults to `http://127.0.0.1:3000`.
- Jan API URL: `PERISCOPE_JAN_API` defaults to `http://127.0.0.1:1337/v1`.
- Optional model fallback for imported chats: `PERISCOPE_DEFAULT_MODEL`; otherwise model IDs are read from Jan metadata if available.

### Phone access

By default the launcher listens on **localhost only**, so your chats are not broadcast to the LAN or internet. For access outside the PC, use a private mesh VPN such as Tailscale and a secure tailnet-only proxy/serve configuration (or another authenticated HTTPS reverse proxy). Do **not** port-forward Jan's `1337` API or disable Open WebUI authentication. The Jan API does not need to be publicly reachable: only the browser's Open WebUI endpoint needs private access.

If you deliberately want LAN-only access on a trusted network, you can set `PERISCOPE_WEBUI_HOST=0.0.0.0` when starting Open WebUI, after creating a strong admin password. That exposes Open WebUI to other devices on your LAN and is **not** an internet-safe replacement for HTTPS.

## Current limitations

- Jan's OpenAI-compatible API is for model inference, not Jan Desktop's editable conversation history.
- The bridge reads Jan Desktop's documented `threads/<id>/thread.json` and `messages.jsonl` structure. It ignores tool-only/non-text message blocks; this is a **text-only** import.
- Conversation files may be absent: `periscope list` then shows none. On the Build-Arch machine inspected during initial development, both Jan and Jan Nightly `data/threads` directories were empty, so an import against real desktop chats has **not** been demonstrated there.
- Existing web conversations do not flow back into Jan Desktop; messages/edits on both sides are **not merged**.
- Open WebUI has its own account, conversation store and chat settings. Jan's assistant instructions do **not** automatically transfer with model access.
- No background service, watch process, Docker daemon, login service or automatic startup is installed.

## Testing

```bash
python -m unittest discover -s tests -v
```

## Roadmap

1. Verify imports against real Jan Nightly chat threads and model metadata.
2. Offer a convenient Link/Unlink interface rather than only CLI commands.
3. Design guarded incremental synchronization with explicit conflict handling and backups.
4. Explore truly bidirectional sync only if Jan provides a supported thread API, or after validating an isolated and reversible integration against the exact installed version.

## Source references

- [Open WebUI: connect an OpenAI-compatible backend](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/)
- [Open WebUI: chat import JSON schema](https://docs.openwebui.com/features/chat-conversations/data-controls/import-export/)
- [Open WebUI: Python / uv launcher](https://docs.openwebui.com/getting-started/quick-start/)
- [Jan: desktop data folder and thread format](https://docs.jan.ai/desktop/data-folder)

MIT License.