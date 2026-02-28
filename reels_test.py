"""
Har xil turdagi postlarni test qilish:
reel, oddiy video, rasm, carousel
"""
from instaapi import Instagram

ig = Instagram()

# Har xil turdagi shortcode'lar
tests = [
    ("DU8nFS-DK03", "Reel"),           # User test qilgan reel
    ("CtjoC2BNsB2", "Reel (pankocat)"),  # Reel
]

for sc, label in tests:
    print(f"[{label}] Shortcode: {sc}")
    print("-" * 50)

    post = ig.public.get_post_by_shortcode(sc)

    if not post:
        print("  Topilmadi\n")
        continue

    mtype = post.get('media_type', 'N/A')
    ptype = post.get('product_type', 'N/A')
    is_video = post.get('is_video', False)

    print(f"  media_type:    {mtype}")
    print(f"  product_type:  {ptype}")
    print(f"  is_video:      {is_video}")
    print(f"  Likes:         {post.get('likes', 0):,}")

    if is_video:
        print(f"  Video URL:     {'BOR' if post.get('video_url') else 'YOQ'}")
        views = post.get('video_view_count') or post.get('video_views', 0)
        print(f"  Views:         {views:,}" if views else "  Views:         N/A")
    
    print(f"  Display URL:   {'BOR' if post.get('display_url') else 'YOQ'}")

    carousel = post.get('carousel_media')
    if carousel:
        print(f"  Carousel:      {len(carousel)} ta rasm/video")
    print(post)
    print()
