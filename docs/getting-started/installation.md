# Installation

## Requirements

- **Python** 3.10+
- **curl_cffi** — TLS fingerprint engine (auto-installed)

## Install from PyPI

```bash
pip install InstaHarvest v2
```

## Install from source

```bash
git clone https://github.com/mpython77/instaharvest_v2.git
cd InstaHarvest v2
pip install -e .
```

## Dependencies

InstaHarvest v2 automatically installs these:

| Package | Purpose |
|---|---|
| `curl_cffi` | HTTP client with TLS fingerprint impersonation |
| `pydantic` | Data models and validation |
| `python-dotenv` | `.env` file loading |
| `pynacl` | NaCl encrypted password login |
| `cryptography` | Cryptographic operations |

## Verify Installation

```python
import instaharvest_v2
print(instaharvest_v2.__version__)
```

## Optional Dependencies

```bash
# AI Agent providers
pip install InstaHarvest v2[agent]    # openai, google-genai, anthropic, rich

# Web playground (FastAPI)
pip install InstaHarvest v2[web]      # fastapi, uvicorn + agent deps

# Development tools
pip install InstaHarvest v2[dev]      # pytest, pytest-asyncio, pytest-cov

# Everything
pip install InstaHarvest v2[all]
```
