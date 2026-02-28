# Installation

## Requirements

- **Python** 3.10+
- **curl_cffi** — TLS fingerprint engine (auto-installed)

## Install from PyPI

```bash
pip install instaapi
```

## Install from source

```bash
git clone https://github.com/mpython77/instaapi.git
cd instaapi
pip install -e .
```

## Dependencies

InstaAPI automatically installs these:

| Package | Purpose |
|---|---|
| `curl_cffi` | HTTP client with TLS fingerprint impersonation |
| `pydantic` | Data models and validation |
| `python-dotenv` | `.env` file loading |
| `pynacl` | NaCl encrypted password login |
| `cryptography` | Cryptographic operations |

## Verify Installation

```python
import instaapi
print(instaapi.__version__)
```

## Optional Dependencies

```bash
# AI Agent providers
pip install instaapi[agent]    # openai, google-genai, anthropic, rich

# Web playground (FastAPI)
pip install instaapi[web]      # fastapi, uvicorn + agent deps

# Development tools
pip install instaapi[dev]      # pytest, pytest-asyncio, pytest-cov

# Everything
pip install instaapi[all]
```
