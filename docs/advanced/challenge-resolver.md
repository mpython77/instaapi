# Challenge Resolver

When logging into an old account from a new IP, Instagram often presents a "Suspicious Login Attempt" challenge requiring 6-digit Email or SMS verification.

InstaAPI provides built-in tools to resolve these automatically (`resolve()`) and headless integrations with Gmail to completely bypass manual intervention.

## Standard Callback Approach

The simplest method is providing a callback function during setup:

```python
from instaapi import Instagram
from instaapi.exceptions import ChallengeRequired

def prompt_for_code(challenge_type, contact_point):
    print(f"Instagram sent a code to your {challenge_type}: {contact_point}")
    return input("Enter the 6-digit code here: ")

ig = Instagram(challenge_callback=prompt_for_code)

try:
    ig.login("my_username", "my_password")
except ChallengeRequired as e:
    # InstaAPI will automatically trigger the prompt_for_code callback, 
    # submit the returned code, and if successful, complete the login.
    print("Handled challenge successfully!")
```

## Headless Auto-Resolver (Gmail)

If the account uses Gmail, you can use the `EmailVerifier` module to automatically scrape the code from the inbox without any prompts.

### 1. Setup Google Cloud API

1. Go to Google Cloud Console.
2. Enable the **Gmail API**.
3. Create an OAuth 2.0 Client ID (Desktop App).
4. Download `credentials.json` and place it in your project root.

### 2. Configure the Auto-Resolver

```python
from instaapi import Instagram
from instaapi.email_verifier import EmailVerifier

# 1. Init verifier
verifier = EmailVerifier("credentials.json", "token.json")

def auto_gmail_resolve(ctype, contact):
    return verifier.get_instagram_code(wait_time=30)

# 2. Bind to Instagram object
ig = Instagram(challenge_callback=auto_gmail_resolve)

# 3. Login
ig.login("my_user", "my_pass")
# If it hits a challenge, it will wait up to 30s, read the Gmail inbox, 
# extract the 6 digits, and resume!
```

## Supported Challenge Types

The internal `ChallengeHandler` module parses and supports:

* `email` (Standard 6-digit email)
* `sms` (Standard 6-digit text)
* `consent` (Terms of Service updates — auto-accepted!)
* `platform` (App-based approval loops)

If a Challenge type is completely unsupported (like a visual CAPTCHA or facial scan), the library will immediately raise a hard `ChallengeRequired` exception stating manual app intervention is needed.
