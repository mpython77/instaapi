# Utilities Reference

Helper functions in `instaharvest_v2.utils` for URL/shortcode conversion and data extraction.

## Shortcode / PK Conversion

### shortcode_to_pk(shortcode: str) → int

Convert Instagram shortcode to media PK.

```python
from instaharvest_v2.utils import shortcode_to_pk

pk = shortcode_to_pk("DVDk2dSjcq_")
# 3124567890123
```

### pk_to_shortcode(pk: int) → str

Convert media PK to shortcode.

```python
from instaharvest_v2.utils import pk_to_shortcode

code = pk_to_shortcode(3124567890123)
# "DVDk2dSjcq_"
```

---

## URL Extraction

### extract_shortcode(url: str) → str | None

Extract shortcode from Instagram URL. Supports `instagram.com/p/`, `instagram.com/reel/`, `instagram.com/tv/`, and `instagr.am/p/`.

```python
from instaharvest_v2.utils import extract_shortcode

code = extract_shortcode("https://www.instagram.com/reel/ABC123/")
# "ABC123"
```

### url_to_media_pk(url: str) → int | None

Convert Instagram URL directly to media PK.

```python
from instaharvest_v2.utils import url_to_media_pk

pk = url_to_media_pk("https://www.instagram.com/p/ABC123/")
```

### media_pk_to_url(media_pk: int) → str

Convert media PK to Instagram URL.

```python
from instaharvest_v2.utils import media_pk_to_url

url = media_pk_to_url(3124567890123)
# "https://www.instagram.com/p/DVDk2dSjcq_/"
```

### extract_username(url: str) → str | None

Extract username from Instagram profile URL.

```python
from instaharvest_v2.utils import extract_username

username = extract_username("https://www.instagram.com/cristiano/")
# "cristiano"
```

### extract_story_pk(url: str) → str | None

Extract story PK from story URL.

```python
from instaharvest_v2.utils import extract_story_pk

pk = extract_story_pk("https://www.instagram.com/stories/nike/12345/")
# "12345"
```

---

## Data Conversion

### media_id_to_pk(media_id: str) → int

Convert media ID (`pk_user_pk` format) to PK.

```python
from instaharvest_v2.utils import media_id_to_pk

pk = media_id_to_pk("1234567890_1234567")
# 1234567890
```

### format_count(count: int) → str

Format number in compact form.

```python
from instaharvest_v2.utils import format_count

format_count(1500)       # "1.5K"
format_count(2500000)    # "2.5M"
format_count(1200000000) # "1.2B"
```
