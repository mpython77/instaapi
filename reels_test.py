"""
Instagram Reels ma'lumotlarini olish testi.
instaapi kutubxonasi orqali anonim (login talab qilinmaydi).
"""
from instaapi import Instagram

# Anonim klient yaratish (login shart emas)
ig = Instagram.anonymous()

username = "cristiano"
print(f"'{username}' foydalanuvchisining reels'larini olmoqdamiz...\n")

# Reels'larni olish (max 3 ta)
reels = ig.public.get_reels(username, max_count=3)

if not reels:
    print("Reels topilmadi yoki xato yuz berdi.")
else:
    print(f"Jami {len(reels)} ta reel topildi:\n")
    for i, reel in enumerate(reels, 1):
        print(f"--- Reel #{i} ---")
        print(f"  ID:         {reel.get('id', 'N/A')}")
        print(f"  Caption:    {(reel.get('caption', '') or '')[:80]}")
        print(f"  Likes:      {reel.get('likes', 0):,}")
        print(f"  Comments:   {reel.get('comments', 0):,}")
        print(f"  Views:      {reel.get('play_count', 0):,}")
        audio = reel.get('audio') or {}
        print(f"  Audio:      {audio.get('title', 'N/A')}")
        print(f"  Timestamp:  {reel.get('timestamp', 'N/A')}")
        print()
