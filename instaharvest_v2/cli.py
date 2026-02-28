"""
InstaAPI CLI — Command-line Interface
======================================
CLI tool for direct usage from the terminal.

Usage:
    python -m instaapi profile cristiano
    python -m instaapi profile cristiano --json
    python -m instaapi export followers cristiano -o followers.csv
    python -m instaapi analytics engagement cristiano
    python -m instaapi analytics compare cristiano messi neymar
    python -m instaapi hashtag analyze python
    python -m instaapi download all cristiano -o downloads/
"""

import argparse
import json
import sys
import os


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instaharvest_v2",
        description="🔥 InstaAPI — Instagram Private API CLI",
    )
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ─── profile ───────────────────────────────────
    p_profile = subparsers.add_parser("profile", help="Get user profile")
    p_profile.add_argument("username", help="Instagram username")
    p_profile.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")

    # ─── export ────────────────────────────────────
    p_export = subparsers.add_parser("export", help="Export data to CSV/JSON")
    export_sub = p_export.add_subparsers(dest="export_type")

    # export followers
    p_exp_foll = export_sub.add_parser("followers", help="Export followers")
    p_exp_foll.add_argument("username", help="Target username")
    p_exp_foll.add_argument("-o", "--output", default="followers.csv", help="Output file")
    p_exp_foll.add_argument("-n", "--count", type=int, default=0, help="Max count (0=all)")

    # export following
    p_exp_fing = export_sub.add_parser("following", help="Export following")
    p_exp_fing.add_argument("username", help="Target username")
    p_exp_fing.add_argument("-o", "--output", default="following.csv", help="Output file")
    p_exp_fing.add_argument("-n", "--count", type=int, default=0, help="Max count")

    # export hashtag
    p_exp_hash = export_sub.add_parser("hashtag", help="Export hashtag users")
    p_exp_hash.add_argument("tag", help="Hashtag")
    p_exp_hash.add_argument("-o", "--output", default="hashtag_users.csv", help="Output file")
    p_exp_hash.add_argument("-n", "--count", type=int, default=100, help="Max count")

    # export json
    p_exp_json = export_sub.add_parser("json", help="Full profile to JSON")
    p_exp_json.add_argument("username", help="Target username")
    p_exp_json.add_argument("-o", "--output", default="profile.json", help="Output file")

    # ─── analytics ─────────────────────────────────
    p_analytics = subparsers.add_parser("analytics", help="Account analytics")
    analytics_sub = p_analytics.add_subparsers(dest="analytics_type")

    p_eng = analytics_sub.add_parser("engagement", help="Engagement rate")
    p_eng.add_argument("username", help="Target username")
    p_eng.add_argument("-n", "--posts", type=int, default=12, help="Posts to analyze")

    p_times = analytics_sub.add_parser("times", help="Best posting times")
    p_times.add_argument("username", help="Target username")

    p_content = analytics_sub.add_parser("content", help="Content analysis")
    p_content.add_argument("username", help="Target username")

    p_summary = analytics_sub.add_parser("summary", help="Full profile summary")
    p_summary.add_argument("username", help="Target username")

    p_compare = analytics_sub.add_parser("compare", help="Compare accounts")
    p_compare.add_argument("usernames", nargs="+", help="Usernames to compare")

    # ─── hashtag ───────────────────────────────────
    p_hashtag = subparsers.add_parser("hashtag", help="Hashtag research")
    hashtag_sub = p_hashtag.add_subparsers(dest="hashtag_type")

    p_ht_analyze = hashtag_sub.add_parser("analyze", help="Analyze a hashtag")
    p_ht_analyze.add_argument("tag", help="Hashtag to analyze")

    p_ht_related = hashtag_sub.add_parser("related", help="Find related hashtags")
    p_ht_related.add_argument("tag", help="Source hashtag")
    p_ht_related.add_argument("-n", "--count", type=int, default=20, help="Max results")

    p_ht_suggest = hashtag_sub.add_parser("suggest", help="Smart suggestions")
    p_ht_suggest.add_argument("tag", help="Seed hashtag")
    p_ht_suggest.add_argument("-n", "--count", type=int, default=20, help="Suggestions count")

    # ─── download ──────────────────────────────────
    p_download = subparsers.add_parser("download", help="Bulk download media")
    download_sub = p_download.add_subparsers(dest="download_type")

    p_dl_posts = download_sub.add_parser("posts", help="Download posts")
    p_dl_posts.add_argument("username", help="Target username")
    p_dl_posts.add_argument("-o", "--output", default="downloads", help="Output dir")
    p_dl_posts.add_argument("-n", "--count", type=int, default=0, help="Max posts")

    p_dl_stories = download_sub.add_parser("stories", help="Download stories")
    p_dl_stories.add_argument("username", help="Target username")
    p_dl_stories.add_argument("-o", "--output", default="downloads", help="Output dir")

    p_dl_all = download_sub.add_parser("all", help="Download everything")
    p_dl_all.add_argument("username", help="Target username")
    p_dl_all.add_argument("-o", "--output", default="downloads", help="Output dir")

    # ─── pipeline ──────────────────────────────────
    p_pipeline = subparsers.add_parser("pipeline", help="Data pipeline")
    pipeline_sub = p_pipeline.add_subparsers(dest="pipeline_type")

    p_sqlite = pipeline_sub.add_parser("sqlite", help="Export to SQLite")
    p_sqlite.add_argument("username", help="Target username")
    p_sqlite.add_argument("-o", "--output", default="data.db", help="Database file")

    p_jsonl = pipeline_sub.add_parser("jsonl", help="Export to JSONL")
    p_jsonl.add_argument("username", help="Target username")
    p_jsonl.add_argument("-o", "--output", default="data.jsonl", help="Output file")

    return parser


def get_ig(env_path: str, debug: bool = False):
    """Initialize Instagram client."""
    from .instagram import Instagram
    return Instagram.from_env(env_path, debug=debug)


def pp(data, as_json: bool = False):
    """Pretty-print data."""
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    print(f"  {k}: {json.dumps(v, ensure_ascii=False, default=str)[:120]}")
                else:
                    print(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                print(f"  {item}")


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    ig = get_ig(args.env, args.debug)

    try:
        if args.command == "profile":
            user = ig.users.get_by_username(args.username)
            if hasattr(user, "__dict__"):
                data = {k: v for k, v in user.__dict__.items() if not k.startswith("_")}
            else:
                data = user
            print(f"\n🔍 @{args.username}")
            pp(data, args.as_json)

        elif args.command == "export":
            if args.export_type == "followers":
                result = ig.export.followers_to_csv(args.username, args.output, max_count=args.count)
                print(f"\n📥 Exported {result['exported']} followers → {result['file']}")
            elif args.export_type == "following":
                result = ig.export.following_to_csv(args.username, args.output, max_count=args.count)
                print(f"\n📥 Exported {result['exported']} following → {result['file']}")
            elif args.export_type == "hashtag":
                result = ig.export.hashtag_users(args.tag, args.output, count=args.count)
                print(f"\n📥 Exported {result['exported']} #{args.tag} users → {result['file']}")
            elif args.export_type == "json":
                result = ig.export.to_json(args.username, args.output)
                print(f"\n📥 Exported → {result['file']}")

        elif args.command == "analytics":
            if args.analytics_type == "engagement":
                result = ig.analytics.engagement_rate(args.username, args.posts)
                print(f"\n📊 @{args.username} Engagement")
                pp(result)
            elif args.analytics_type == "times":
                result = ig.analytics.best_posting_times(args.username)
                print(f"\n📊 @{args.username} Best Posting Times")
                pp(result)
            elif args.analytics_type == "content":
                result = ig.analytics.content_analysis(args.username)
                print(f"\n📊 @{args.username} Content Analysis")
                pp(result)
            elif args.analytics_type == "summary":
                result = ig.analytics.profile_summary(args.username)
                print(f"\n📊 @{args.username} Full Summary")
                pp(result, True)
            elif args.analytics_type == "compare":
                result = ig.analytics.compare(args.usernames)
                print(f"\n📊 Comparison: {' vs '.join(args.usernames)}")
                print(f"  🏆 Winner: @{result['winner']}")
                for acc in result["accounts"]:
                    eng = acc.get("engagement_rate", 0)
                    fol = acc.get("followers", 0)
                    print(f"  @{acc['username']}: {fol:,} followers | {eng:.2f}% engagement")

        elif args.command == "hashtag":
            if args.hashtag_type == "analyze":
                result = ig.hashtag_research.analyze(args.tag)
                print(f"\n🔍 #{args.tag} Analysis")
                pp(result)
            elif args.hashtag_type == "related":
                result = ig.hashtag_research.related(args.tag, args.count)
                print(f"\n🔗 #{args.tag} Related Tags ({len(result)})")
                for r in result:
                    print(f"  #{r['name']} (co-occurrence: {r['co_occurrence']})")
            elif args.hashtag_type == "suggest":
                result = ig.hashtag_research.suggest(args.tag, args.count)
                print(f"\n💡 #{args.tag} Suggestions ({len(result)})")
                for s in result:
                    print(f"  #{s['name']} [{s['difficulty']}] ({s['media_count']:,} posts)")

        elif args.command == "download":
            if args.download_type == "posts":
                result = ig.bulk_download.all_posts(args.username, args.output, max_count=args.count)
                print(f"\n📦 Downloaded {result['downloaded']} posts → {result['output_dir']}")
            elif args.download_type == "stories":
                result = ig.bulk_download.all_stories(args.username, args.output)
                print(f"\n📦 Downloaded {result['downloaded']} stories")
            elif args.download_type == "all":
                result = ig.bulk_download.everything(args.username, args.output)
                print(f"\n📦 Downloaded {result['total_files']} total files → {args.output}")

        elif args.command == "pipeline":
            if args.pipeline_type == "sqlite":
                result = ig.pipeline.to_sqlite(args.username, args.output)
                print(f"\n🗄️ {result['rows_inserted']} rows → {result['file']}")
            elif args.pipeline_type == "jsonl":
                result = ig.pipeline.to_jsonl(args.username, args.output)
                print(f"\n📄 {result['lines_written']} lines → {result['file']}")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
