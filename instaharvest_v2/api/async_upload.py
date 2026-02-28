"""
Upload API
==========
Upload photos, videos, stories, and reels.

Instagram upload process:
    1. Send binary file to rupload endpoint -> get upload_id
    2. Configure media (caption, location, tags) -> get media_id

Endpoints:
    /rupload_igphoto/{upload_id}         -> Photo upload
    /rupload_igvideo/{upload_id}         -> Video upload
    /media/configure/                    -> Publish as post
    /media/configure_to_story/           -> Publish as story
    /media/configure_to_clips/           -> Publish as reel
"""

import json
import time
import uuid
import os
from typing import Any, Dict, List, Optional

from ..async_client import AsyncHttpClient

# Upload URL — web session only works on www.instagram.com
UPLOAD_URL = "https://www.instagram.com"


class AsyncUploadAPI:
    """Instagram Media Upload API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    # ─── UTILITY ────────────────────────────────────────────

    def _generate_upload_id(self) -> str:
        """Unique upload ID (millisecond timestamp)"""
        return str(int(time.time() * 1000))

    async def _get_session(self):
        """Get current session."""
        return await self._client.get_session()

    # ─── PHOTO UPLOAD ──────────────────────────────────────

    async def _upload_photo(self, image_data: bytes, upload_id: str = None) -> Dict[str, Any]:
        """
        Upload image to Instagram server (raw binary upload).
        """
        upload_id = upload_id or self._generate_upload_id()
        name = f"fb_uploader_{upload_id}"
        upload_url = f"{UPLOAD_URL}/rupload_igphoto/{name}"

        headers = {
            "x-instagram-rupload-params": json.dumps({
                "media_type": 1,
                "upload_id": upload_id,
                "upload_media_height": 1080,
                "upload_media_width": 1080,
            }),
            "x-entity-name": name,
            "x-entity-length": str(len(image_data)),
            "content-type": "application/octet-stream",
            "content-length": str(len(image_data)),
            "offset": "0",
        }

        result = await self._client.upload_raw(
            url=upload_url,
            data=image_data,
            headers=headers,
            rate_category="post_default",
        )
        return result

    async def _upload_video(
        self,
        video_data: bytes,
        upload_id: str = None,
        duration: float = 0,
        width: int = 1080,
        height: int = 1920,
        is_clips: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload video to Instagram server.

        Args:
            video_data: MP4 bytes
            upload_id: Custom upload ID (optional)
            duration: Video duration (seconds)
            width: Video width
            height: Video height
            is_clips: True for Reel

        Returns:
            dict: {upload_id, status, ...}
        """
        upload_id = upload_id or self._generate_upload_id()
        name = f"fb_uploader_{upload_id}"

        upload_url = f"{UPLOAD_URL}/rupload_igvideo/{name}"

        rupload_params = {
            "media_type": 2,  # 2=video
            "upload_id": upload_id,
            "upload_media_height": height,
            "upload_media_width": width,
            "upload_media_duration_ms": int(duration * 1000),
        }

        if is_clips:
            rupload_params["is_clips_video"] = "1"

        headers = {
            "x-instagram-rupload-params": json.dumps(rupload_params),
            "x-entity-name": name,
            "x-entity-length": str(len(video_data)),
            "content-type": "application/octet-stream",
            "content-length": str(len(video_data)),
            "offset": "0",
        }

        result = await self._client.upload_raw(
            url=upload_url,
            data=video_data,
            headers=headers,
            rate_category="post_default",
        )
        return result

    # ─── POST PHOTO ─────────────────────────────────────────

    async def post_photo(
        self,
        image_path: str = None,
        image_data: bytes = None,
        caption: str = "",
        location: Optional[Dict] = None,
        usertags: Optional[List[Dict]] = None,
        disable_comments: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload image as a post.

        Args:
            image_path: File path to image (JPEG/PNG)
            image_data: Image bytes (instead of path)
            caption: Post caption (hashtags, mentions)
            location: {"pk": ..., "name": ..., "lat": ..., "lng": ...}
            usertags: [{"user_id": pk, "position": [x, y]}]
            disable_comments: Disable comments

        Returns:
            dict: {media: {pk, id, code, ...}, status}
        """
        if image_path:
            with open(image_path, "rb") as f:
                image_data = f.read()

        if not image_data:
            raise ValueError("image_path or image_data must be provided!")

        # 1. Upload
        upload_id = self._generate_upload_id()
        upload_result = await self._upload_photo(image_data, upload_id)

        if upload_result.get("status") != "ok":
            return upload_result

        # 2. Configure
        time.sleep(1)

        configure_data = {
            "upload_id": upload_id,
            "caption": caption,
            "source_type": "4",
            "disable_comments": "1" if disable_comments else "0",
        }

        if location:
            configure_data["location"] = json.dumps({
                "name": location.get("name", ""),
                "lat": location.get("lat", 0),
                "lng": location.get("lng", 0),
                "external_source": location.get("external_source", "facebook_places"),
                "facebook_places_id": location.get("pk", location.get("facebook_places_id", "")),
            })

        if usertags:
            tags_in = [{"user_id": str(t["user_id"]), "position": t.get("position", [0.5, 0.5])} for t in usertags]
            configure_data["usertags"] = json.dumps({"in": tags_in})

        return await self._client.post(
            "/media/configure/",
            data=configure_data,
            rate_category="post_default",
        )

    # ─── POST VIDEO ─────────────────────────────────────────

    async def post_video(
        self,
        video_path: str = None,
        video_data: bytes = None,
        thumbnail_path: str = None,
        thumbnail_data: bytes = None,
        caption: str = "",
        duration: float = 0,
        width: int = 1080,
        height: int = 1920,
        location: Optional[Dict] = None,
        disable_comments: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload video as a post.

        Args:
            video_path: File path to video (MP4)
            video_data: Video bytes
            thumbnail_path: Cover image path (optional)
            thumbnail_data: Cover image bytes (optional)
            caption: Post caption
            duration: Video duration (seconds)
            width: Video width
            height: Video height
            location: Location data

        Returns:
            dict: {media: {...}, status}
        """
        if video_path:
            with open(video_path, "rb") as f:
                video_data = f.read()

        if not video_data:
            raise ValueError("video_path or video_data must be provided!")

        # 1. Video upload
        upload_id = self._generate_upload_id()
        upload_result = await self._upload_video(
            video_data, upload_id, duration, width, height,
        )

        # 2. Thumbnail upload (optional)
        if thumbnail_path:
            with open(thumbnail_path, "rb") as f:
                thumbnail_data = f.read()

        if thumbnail_data:
            await self._upload_photo(thumbnail_data, upload_id)

        # 3. Configure
        time.sleep(3)  # Video processing for

        configure_data = {
            "upload_id": upload_id,
            "caption": caption,
            "source_type": "4",
            "disable_comments": "1" if disable_comments else "0",
            "clips_uses_original_audio": "1",
        }

        if location:
            configure_data["location"] = json.dumps({
                "name": location.get("name", ""),
                "lat": location.get("lat", 0),
                "lng": location.get("lng", 0),
            })

        return await self._client.post(
            "/media/configure/?video=1",
            data=configure_data,
            rate_category="post_default",
        )

    # ─── STORY ──────────────────────────────────────────────

    async def post_story_photo(
        self,
        image_path: str = None,
        image_data: bytes = None,
    ) -> Dict[str, Any]:
        """
        Upload image as a story.

        Args:
            image_path: Image path
            image_data: Image bytes

        Returns:
            dict: {media: {pk, ...}, status}
        """
        if image_path:
            with open(image_path, "rb") as f:
                image_data = f.read()

        if not image_data:
            raise ValueError("image_path or image_data must be provided!")

        upload_id = self._generate_upload_id()
        await self._upload_photo(image_data, upload_id)

        time.sleep(1)

        return await self._client.post(
            "/media/configure_to_story/",
            data={
                "upload_id": upload_id,
                "source_type": "4",
            },
            rate_category="post_default",
        )

    async def post_story_video(
        self,
        video_path: str = None,
        video_data: bytes = None,
        duration: float = 0,
    ) -> Dict[str, Any]:
        """
        Upload video as a story.

        Args:
            video_path: Video path (max 15 seconds)
            video_data: Video bytes
            duration: Duration

        Returns:
            dict: {media: {pk, ...}, status}
        """
        if video_path:
            with open(video_path, "rb") as f:
                video_data = f.read()

        if not video_data:
            raise ValueError("video_path or video_data must be provided!")

        upload_id = self._generate_upload_id()
        await self._upload_video(video_data, upload_id, duration)

        time.sleep(3)

        return await self._client.post(
            "/media/configure_to_story/?video=1",
            data={
                "upload_id": upload_id,
                "source_type": "4",
            },
            rate_category="post_default",
        )

    # ─── REEL ───────────────────────────────────────────────

    async def post_reel(
        self,
        video_path: str = None,
        video_data: bytes = None,
        thumbnail_path: str = None,
        thumbnail_data: bytes = None,
        caption: str = "",
        duration: float = 0,
        width: int = 1080,
        height: int = 1920,
    ) -> Dict[str, Any]:
        """
        Upload as a Reel (Clips).

        Args:
            video_path: File path to video (MP4)
            video_data: Video bytes
            thumbnail_path: Cover image path
            thumbnail_data: Cover image bytes
            caption: Reel text
            duration: Video duration
            width: Video width
            height: Video height

        Returns:
            dict: {media: {...}, status}
        """
        if video_path:
            with open(video_path, "rb") as f:
                video_data = f.read()

        if not video_data:
            raise ValueError("video_path or video_data must be provided!")

        upload_id = self._generate_upload_id()
        await self._upload_video(
            video_data, upload_id, duration, width, height, is_clips=True,
        )

        if thumbnail_path:
            with open(thumbnail_path, "rb") as f:
                thumbnail_data = f.read()

        if thumbnail_data:
            await self._upload_photo(thumbnail_data, upload_id)

        time.sleep(3)

        return await self._client.post(
            "/media/configure_to_clips/",
            data={
                "upload_id": upload_id,
                "caption": caption,
                "source_type": "4",
                "clips_uses_original_audio": "1",
            },
            rate_category="post_default",
        )

    # ─── DELETE ─────────────────────────────────────────────

    async def delete_media(self, media_id: int | str, media_type: int = 1) -> Dict[str, Any]:
        """
        Delete post.

        Args:
            media_id: Media PK
            media_type: 1=photo, 2=video, 8=carousel

        Returns:
            dict: {status, did_delete}
        """
        return await self._client.post(
            f"/media/{media_id}/delete/",
            data={"media_type": str(media_type)},
            rate_category="post_default",
        )

    # ─── CAROUSEL (SIDECAR) ──────────────────────────────────

    async def post_carousel(
        self,
        images: List[str | bytes] = None,
        caption: str = "",
        location: Optional[Dict] = None,
        usertags: Optional[List[Dict]] = None,
        disable_comments: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload multi-image post (carousel/album/sidecar).

        Args:
            images: List of images — file path (str) or bytes.
                    Minimum 2, maximum 10 images.
                    Example: ["photo1.jpg", "photo2.jpg"]
                    or: [open("1.jpg","rb").read(), open("2.jpg","rb").read()]
            caption: Post caption
            location: {"pk": ..., "name": ..., "lat": ..., "lng": ...}
            usertags: [{"user_id": pk, "position": [x, y]}]
            disable_comments: Disable comments

        Returns:
            dict: {media: {pk, id, code, carousel_media, ...}, status}
        """
        if not images or len(images) < 2:
            raise ValueError("Carousel requires at least 2 images!")
        if len(images) > 10:
            raise ValueError("Carousel maximum is 10 images!")

        # 1. Upload each image
        children_metadata = []

        for i, img in enumerate(images):
            # File path or bytes
            if isinstance(img, str):
                with open(img, "rb") as f:
                    image_data = f.read()
            else:
                image_data = img

            upload_id = self._generate_upload_id()
            # Unique ID per upload — 1ms apart
            time.sleep(0.01)

            name = f"fb_uploader_{upload_id}"
            upload_url = f"{UPLOAD_URL}/rupload_igphoto/{name}"

            headers = {
                "x-instagram-rupload-params": json.dumps({
                    "media_type": 1,
                    "upload_id": upload_id,
                    "upload_media_height": 1080,
                    "upload_media_width": 1080,
                    "is_sidecar": "1",
                }),
                "x-entity-name": name,
                "x-entity-length": str(len(image_data)),
                "content-type": "application/octet-stream",
                "content-length": str(len(image_data)),
                "offset": "0",
            }

            result = await self._client.upload_raw(
                url=upload_url,
                data=image_data,
                headers=headers,
                rate_category="post_default",
            )

            if result.get("status") != "ok":
                return {
                    "status": "fail",
                    "message": f"Image #{i+1} upload error: {result}",
                }

            children_metadata.append({
                "upload_id": upload_id,
                "source_type": "4",
                "caption": "",
            })

        # 2. Configure sidecar
        time.sleep(1)

        configure_data = {
            "caption": caption,
            "client_sidecar_id": self._generate_upload_id(),
            "children_metadata": json.dumps(children_metadata),
            "disable_comments": "1" if disable_comments else "0",
        }

        if location:
            configure_data["location"] = json.dumps({
                "name": location.get("name", ""),
                "lat": location.get("lat", 0),
                "lng": location.get("lng", 0),
                "external_source": location.get("external_source", "facebook_places"),
                "facebook_places_id": location.get("pk", location.get("facebook_places_id", "")),
            })

        if usertags:
            tags_in = [{"user_id": str(t["user_id"]), "position": t.get("position", [0.5, 0.5])} for t in usertags]
            configure_data["usertags"] = json.dumps({"in": tags_in})

        return await self._client.post(
            "/media/configure_sidecar/",
            data=configure_data,
            rate_category="post_default",
        )
