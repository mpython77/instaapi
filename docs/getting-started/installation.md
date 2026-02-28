# Installation

## Requirements

- **Python** 3.10+
- **curl_cffi** — TLS fingerprint engine (auto-installed)

## Install from PyPI

```bash
pip install insaapi
```

## Install from source

```bash
git clone https://github.com/insaapi/insaapi.git
cd insaapi
pip install -e .
```

## Dependencies

InstaAPI automatically installs these:

| Package | Purpose |
|---|---|
| `curl_cffi` | HTTP client with TLS fingerprint impersonation |
| `pydantic` | Data models and validation |
| `python-dotenv` | `.env` file loading |

## Verify Installation

```python
import instaapi
print(instaapi.__version__)
```

## Optional Dependencies

```bash
# For Gmail challenge auto-resolver
pip install google-auth google-auth-oauthlib google-api-python-client

# For export to Excel
pip install openpyxl

# For AI suggestions
pip install google-generativeai
```
