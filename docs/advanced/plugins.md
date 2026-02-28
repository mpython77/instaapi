# Plugin System

InstaAPI is built around a flexible plugin architecture. Every internal module (UsersAPI, SearchAPI, etc.) is technically a plugin hooked into the core client context.

You can create your own plugins to inject custom middleware, handle state, or automate complex multi-step processes securely.

## Quick Example

```python
from instaharvest_v2 import Instagram
from instaharvest_v2.plugin import Plugin

class AutoLikerPlugin(Plugin):
    """Automatically likes any post fetched by get_post_by_shortcode"""
    
    name = "auto_liker"
    
    def on_attach(self):
        # Bind to standard client events
        self.ig.on("api_request_success", self._check_for_posts)

    def _check_for_posts(self, data):
        url = data.get("url", "")
        if "media/info" in url:
            # Fake parsing to grab the PK and automatically like it
            # This is an example of intercepting network streams via plugins
            print("Auto-liker intercepted a media load!")

ig = Instagram.from_env()
ig.use(AutoLikerPlugin()) # Install the plugin
```

## Building a Basic Plugin

Plugins must subclass `instaharvest_v2.plugin.Plugin` and specify a string `name`. They are automatically injected with the main client instance as `self.ig`.

```python
class MyCustomTool(Plugin):
    name = "my_custom_tool"
    
    def on_attach(self):
        print(f"Plugin {self.name} attached to client!")
        
    def do_something_cool(self):
        # Access the main IG client directly
        return self.ig.users.get_by_username("cristiano")
```

Once a plugin is injected via `ig.use()`, it becomes accessible via standard dot-notation using its `name`:

```python
ig.use(MyCustomTool())

user = ig.my_custom_tool.do_something_cool()
```

## Writing Custom APIs

It's recommended to write any complex scripts you use frequently as a Plugin to easily bundle and distribute them without hacking the core library:

```python
class CleanerPlugin(Plugin):
    name = "cleaner"
    
    def unfollow_non_followers(self):
        followers = self.ig.friendships.get_followers(self.ig.user_id)
        following = self.ig.friendships.get_following(self.ig.user_id)
        
        follower_pks = {u.pk for u in followers}
        for u in following:
            if u.pk not in follower_pks:
                self.ig.friendships.unfollow(u.pk)
                print(f"Unfollowed {u.username}")

ig.use(CleanerPlugin())
ig.cleaner.unfollow_non_followers()
```

## Default Core Plugins

InstaAPI uses the plugin system internally for extending "Tools" (like Batch, Automation, Scheduler). If you examine the code for `GrowthAPI`, you will see it relies heavily on the `Plugin` class structure.
