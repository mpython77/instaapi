# InsightsAPI

> `ig.insights` — Account statistics, post performance, business info, and ad accounts.

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

# Account summary
summary = ig.insights.get_account_summary()
print(summary)

# Single post stats
stats = ig.insights.get_media_insights(3124567890123)
print(stats)
```

## Methods

### get_account_summary()

Get overall account statistics (reach, impressions, followers growth).

**Returns:** `dict` — account-level analytics

---

### get_media_insights(media_id)

Get performance analytics for a single post.

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK |

**Returns:** `dict` — reach, impressions, saves, shares, engagement

---

### get_business_info(user_id)

Get business/creator account info and linked Facebook page.

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | User PK |

**Returns:** `dict`

---

### get_ads_accounts()

Get linked Facebook Ads accounts.

**Returns:** `dict` — ads accounts list

!!! note
    Insights endpoints require a **Business** or **Creator** account.
