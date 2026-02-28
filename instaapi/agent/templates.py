"""
Agent Templates — Pre-built Task Templates
============================================
Ready-to-use templates for common Instagram tasks.

Templates:
    - profile_analysis  — Full profile analysis
    - compare_accounts  — Compare multiple accounts
    - export_followers  — Export followers to CSV
    - best_posting_time — Find optimal posting times
    - hashtag_research  — Hashtag analysis
    - engagement_report — Engagement rate report
    - content_calendar  — Content planning
    - competitor_spy    — Competitor analysis
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("instaapi.agent.templates")


@dataclass
class TaskTemplate:
    """A pre-built task template."""
    name: str
    title: str
    description: str
    prompt: str
    required_params: List[str]
    optional_params: List[str]
    category: str
    estimated_steps: int
    requires_login: bool = False

    def render(self, **kwargs) -> str:
        """Render template with parameters."""
        prompt = self.prompt
        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt


# ═══════════════════════════════════════════════════════════
# TEMPLATE REGISTRY
# ═══════════════════════════════════════════════════════════

TEMPLATES: Dict[str, TaskTemplate] = {}


def register_template(template: TaskTemplate):
    """Register a template in the global registry."""
    TEMPLATES[template.name] = template
    return template


def get_template(name: str) -> Optional[TaskTemplate]:
    """Get template by name."""
    return TEMPLATES.get(name)


def list_templates(category: Optional[str] = None) -> List[TaskTemplate]:
    """List all templates, optionally filtered by category."""
    templates = list(TEMPLATES.values())
    if category:
        templates = [t for t in templates if t.category == category]
    return sorted(templates, key=lambda t: t.name)


# ═══════════════════════════════════════════════════════════
# BUILT-IN TEMPLATES
# ═══════════════════════════════════════════════════════════

register_template(TaskTemplate(
    name="profile_analysis",
    title="📊 Full Profile Analysis",
    description="Complete analysis of an Instagram profile including "
                "followers, engagement, posting patterns, and content.",
    prompt=(
        "Perform a complete analysis of @{username}'s Instagram profile:\n\n"
        "1. Get profile info (followers, following, bio, verified status)\n"
        "2. Analyze last {post_count} posts (likes, comments, engagement)\n"
        "3. Calculate engagement rate\n"
        "4. Find best posting times\n"
        "5. Identify top-performing content\n"
        "6. Create a summary report\n\n"
        "Save the results to {output_file}"
    ),
    required_params=["username"],
    optional_params=["post_count", "output_file"],
    category="analytics",
    estimated_steps=8,
))

register_template(TaskTemplate(
    name="compare_accounts",
    title="⚖️ Account Comparison",
    description="Side-by-side comparison of multiple Instagram accounts.",
    prompt=(
        "Compare these Instagram accounts: {usernames}\n\n"
        "For each account:\n"
        "1. Get follower count, following count, post count\n"
        "2. Calculate engagement rate (last 12 posts)\n"
        "3. Analyze posting frequency\n"
        "4. Compare content types\n\n"
        "Create a comparison table and determine the winner.\n"
        "Save results to {output_file}"
    ),
    required_params=["usernames"],
    optional_params=["output_file"],
    category="analytics",
    estimated_steps=10,
))

register_template(TaskTemplate(
    name="export_followers",
    title="📥 Export Followers to CSV",
    description="Export an account's followers list to a CSV file.",
    prompt=(
        "Export @{username}'s followers to CSV:\n\n"
        "1. Get all followers (max {max_count})\n"
        "2. For each follower: username, full_name, is_verified, is_private\n"
        "3. Save to {output_file}\n"
        "4. Report total count"
    ),
    required_params=["username"],
    optional_params=["max_count", "output_file"],
    category="export",
    estimated_steps=5,
    requires_login=True,
))

register_template(TaskTemplate(
    name="best_posting_time",
    title="⏰ Best Posting Time",
    description="Analyze when a user's posts get the most engagement.",
    prompt=(
        "Find the best posting times for @{username}:\n\n"
        "1. Get last {post_count} posts with timestamps\n"
        "2. Analyze engagement by hour and day\n"
        "3. Find peak engagement windows\n"
        "4. Create a chart showing engagement by time\n"
        "5. Recommend optimal posting schedule"
    ),
    required_params=["username"],
    optional_params=["post_count"],
    category="analytics",
    estimated_steps=6,
))

register_template(TaskTemplate(
    name="hashtag_research",
    title="#️⃣ Hashtag Research",
    description="Research and analyze hashtags for a topic or niche.",
    prompt=(
        "Research hashtags for the topic: '{topic}'\n\n"
        "1. Search for related hashtags\n"
        "2. Get post counts for each\n"
        "3. Categorize by size (small/medium/large)\n"
        "4. Suggest an optimal hashtag mix (30 hashtags)\n"
        "5. Save results to {output_file}"
    ),
    required_params=["topic"],
    optional_params=["output_file"],
    category="research",
    estimated_steps=6,
))

register_template(TaskTemplate(
    name="engagement_report",
    title="📈 Engagement Report",
    description="Detailed engagement analysis with charts.",
    prompt=(
        "Create an engagement report for @{username}:\n\n"
        "1. Get last {post_count} posts\n"
        "2. Calculate: avg likes, avg comments, engagement rate\n"
        "3. Find top 5 and bottom 5 posts\n"
        "4. Create bar chart of top posts\n"
        "5. Analyze engagement trends (improving/declining)\n"
        "6. Save report to {output_file}"
    ),
    required_params=["username"],
    optional_params=["post_count", "output_file"],
    category="analytics",
    estimated_steps=8,
))

register_template(TaskTemplate(
    name="content_calendar",
    title="📅 Content Calendar",
    description="Generate a content posting calendar based on analytics.",
    prompt=(
        "Create a 7-day content calendar for @{username}:\n\n"
        "1. Analyze their best posting times\n"
        "2. Identify top-performing content types\n"
        "3. Suggest post ideas based on their niche\n"
        "4. Recommend hashtags for each post\n"
        "5. Create a weekly schedule (date, time, content type, hashtags)\n"
        "6. Save to {output_file}"
    ),
    required_params=["username"],
    optional_params=["output_file"],
    category="planning",
    estimated_steps=8,
))

register_template(TaskTemplate(
    name="competitor_spy",
    title="🕵️ Competitor Analysis",
    description="Deep analysis of competitor accounts.",
    prompt=(
        "Analyze competitor @{username}:\n\n"
        "1. Profile overview (followers, growth indicators)\n"
        "2. Content strategy (post types, frequency, timing)\n"
        "3. Top performing content (last {post_count} posts)\n"
        "4. Hashtag usage patterns\n"
        "5. Engagement benchmarks\n"
        "6. Strengths and weaknesses\n"
        "7. Actionable insights for competing\n"
        "8. Save analysis to {output_file}"
    ),
    required_params=["username"],
    optional_params=["post_count", "output_file"],
    category="analytics",
    estimated_steps=10,
))

register_template(TaskTemplate(
    name="scrape_posts",
    title="📋 Scrape Posts",
    description="Scrape and save a user's posts with all metadata.",
    prompt=(
        "Scrape @{username}'s posts:\n\n"
        "1. Get last {post_count} posts\n"
        "2. Extract: caption, likes, comments, date, media type, shortcode\n"
        "3. Save all data to {output_file}\n"
        "4. Show summary stats"
    ),
    required_params=["username"],
    optional_params=["post_count", "output_file"],
    category="export",
    estimated_steps=4,
))

register_template(TaskTemplate(
    name="dm_campaign",
    title="✉️ DM Campaign",
    description="Send personalized DMs to a list of users.",
    prompt=(
        "Run a DM campaign:\n\n"
        "1. Read target usernames from {input_file}\n"
        "2. For each user, send this message: '{message}'\n"
        "3. Personalize with their name if available\n"
        "4. Add {delay} second delay between messages\n"
        "5. Log results to {output_file}\n"
        "6. Report success/failure count"
    ),
    required_params=["input_file", "message"],
    optional_params=["delay", "output_file"],
    category="automation",
    estimated_steps=6,
    requires_login=True,
))


# ═══════════════════════════════════════════════════════════
# TEMPLATE RUNNER
# ═══════════════════════════════════════════════════════════

class TemplateRunner:
    """
    Execute templates through the agent.

    Usage:
        runner = TemplateRunner(agent)
        result = runner.run("profile_analysis", username="cristiano")
        templates = runner.list()
    """

    def __init__(self, agent):
        self._agent = agent

    def run(self, template_name: str, **kwargs):
        """Run a template with given parameters."""
        template = get_template(template_name)
        if not template:
            available = ", ".join(TEMPLATES.keys())
            raise ValueError(
                f"Template '{template_name}' not found. "
                f"Available: {available}"
            )

        # Set defaults for optional params
        defaults = {
            "post_count": "12",
            "max_count": "1000",
            "output_file": f"{template_name}_result.json",
            "delay": "5",
            "input_file": "users.txt",
        }
        for key in template.optional_params:
            if key not in kwargs:
                kwargs[key] = defaults.get(key, "")

        # Check required params
        missing = [p for p in template.required_params if p not in kwargs]
        if missing:
            raise ValueError(
                f"Missing required parameters: {', '.join(missing)}"
            )

        # Render and execute
        prompt = template.render(**kwargs)
        logger.info(f"Running template: {template.title}")

        return self._agent.ask(prompt)

    def list(self, category: Optional[str] = None) -> List[Dict]:
        """List available templates."""
        templates = list_templates(category)
        return [
            {
                "name": t.name,
                "title": t.title,
                "description": t.description,
                "category": t.category,
                "required_params": t.required_params,
                "requires_login": t.requires_login,
            }
            for t in templates
        ]
