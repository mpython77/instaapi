# Vision (Image Analysis)

`VisionAnalyzer` enables the agent to analyze images using AI vision capabilities.

## Supported Providers

| Provider | Model | Vision Support |
| --- | --- | --- |
| **OpenAI** | GPT-4.1 / GPT-4o | ✅ Full |
| **Google Gemini** | Gemini 3.x / 2.5 | ✅ Full |
| **Anthropic Claude** | Claude 4.6 / 4 | ✅ Full |
| Others | — | ❌ Not supported |

## Usage

### Analyze Local Image

```python
from instaapi.agent.vision import VisionAnalyzer
from instaapi.agent.providers import get_provider

provider = get_provider("gemini", api_key="AIza...")
vision = VisionAnalyzer(provider)

# Analyze a downloaded photo
result = vision.analyze_image(
    "photo.jpg",
    prompt="Describe this Instagram post. What's in the image?",
    language="en",
)
print(result)
```

### Analyze Image from URL

```python
result = vision.analyze_url(
    "https://instagram.com/..../photo.jpg",
    prompt="What products are shown in this image?",
    language="en",
)
```

### Check Provider Support

```python
if vision.is_supported:
    result = vision.analyze_image("photo.jpg")
else:
    print("Current provider doesn't support vision")
```

## Parameters

### `analyze_image(image_path, prompt, language)`

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| `image_path` | `str` | required | Path to local image file |
| `prompt` | `str` | `"Describe this image in detail."` | Analysis prompt |
| `language` | `str` | `"en"` | Response language |

### `analyze_url(image_url, prompt, language)`

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| `image_url` | `str` | required | Image URL |
| `prompt` | `str` | `"Describe this image in detail."` | Analysis prompt |
| `language` | `str` | `"en"` | Response language |

## Supported Formats

- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- WebP (`.webp`)

**Max image size**: 5 MB
