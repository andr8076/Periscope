# Periscope: direct model serving on Build-Arch

This mode runs existing local GGUF model files using `llama-server` instead of Jan or Ollama.

## First run

```bash
git clone https://github.com/andr8076/Periscope.git
cd Periscope
./scripts/start-llama-router.sh
```

The script scans your existing model folders (Jan's SmollSSD library, custom models, and Storyteller) and creates symbolic links in `~/.local/share/periscope/model-links`. Original files stay in place. No additional model files are downloaded, imported or copied. To add another source directory:

```bash
PERISCOPE_MODEL_SOURCES="/some/other/models" ./scripts/start-llama-router.sh
```

Open a separate terminal and verify:

```bash
curl -fsS http://127.0.0.1:18090/health
curl -fsS http://127.0.0.1:18090/v1/models
```

In the existing Open WebUI installation (`http://127.0.0.1:8080` on Build-Arch), sign in as admin and open **Settings → Admin → Connections → Add OpenAI connection**. Use:

- **Base URL:** `http://127.0.0.1:18090/v1`
- **API key:** `local-llama` (arbitrary nonempty placeholder; llama.cpp has no key configured)
- **Provider:** `llama.cpp` if the Advanced provider selector is available
- **Model IDs:** leave empty, so Open WebUI discovers them automatically

Save. Open WebUI is a separate, already-running service; it stores browser and phone conversations in its central database.

The model API is bound to **127.0.0.1 only**. Your phone connects to Open WebUI (with its own login), **not** to this API. Don't port-forward 18090 to the internet.

## Runtime controls

- `PERISCOPE_CTX_SIZE=16384 ./scripts/start-llama-router.sh` requests a longer context (uses more VRAM).
- `PERISCOPE_LLAMA_PORT=18091 ./scripts/start-llama-router.sh` changes the port.
- `PERISCOPE_MODEL_DIR=/some/catalog ./scripts/start-llama-router.sh` changes where links are stored.
- Re-run `python3 scripts/refresh-model-links.py` after adding models, then restart the router.
- Press **Ctrl+C** or close its terminal to stop. It does not run on login.

## Why links rather than duplicate GGUFs?

`llama-server --models-dir` discovers GGUF files within the model directory and subdirectories. A symlink points at the original file; it takes almost no extra disk space. Multimodal GGUFs and their `mmproj` projectors are grouped together.

The catalogue only excludes known embedding models and `mmproj` files as standalone entries. Not every GGUF is necessarily compatible with the installed llama.cpp build. If a model won't load, inspect the terminal output rather than modifying the original file.

The router has `--models-max 1`, so changing models unloads the previous one to conserve GPU memory. The script uses ROCm acceleration when the installed llama.cpp backend supports it.

## Notes about the existing Open WebUI service

Open WebUI is installed on Build-Arch as an existing systemd service and was already running on port 8080. Periscope does **not** change that service, modify its database or create another systemd service.

The connection must be added through your authenticated admin account. Periscope does not access or invent admin credentials.
