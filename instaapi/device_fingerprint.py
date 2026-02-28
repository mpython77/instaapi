"""
Device Fingerprint
==================
Android device emulation inspired by FingerprintJS architecture.
Generates realistic, consistent device fingerprints for Instagram Private API.

Architecture (like FingerprintJS but server-side for Android):
    1. SIGNAL COLLECTION — real device specs from DB
    2. DETERMINISTIC IDs — same seed = same device, always
    3. COHERENT OUTPUT — model + android_version + dpi all match
    4. PERSISTENCE — save/load fingerprints to reuse

Usage:
    # Auto-generate (one-time, then reuse)
    fp = DeviceFingerprint.generate("my_account")
    
    # Get all IDs
    fp.device_id      → "android-7f3b8c2a1d4e9f0a"
    fp.phone_id       → "a1b2c3d4-e5f6-7890-abcd-..."
    fp.uuid           → "f8e7d6c5-b4a3-9281-..."
    fp.user_agent     → "Instagram 332.0.0.64 Android ..."
    fp.headers        → dict with all X-IG-* headers
    
    # Save/load  
    fp.save("device.json")
    fp = DeviceFingerprint.load("device.json")
"""

import hashlib
import json
import logging
import os
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.device_fingerprint")


# ─── REAL DEVICE DATABASE ────────────────────────────────────
# Source: GSMArena + real device traffic captures
# Each entry = real Android phone with accurate specs

DEVICE_DATABASE: List[Dict[str, Any]] = [
    # ─── Samsung Galaxy (2024-2025) ─────────────────
    {
        "manufacturer": "Samsung",
        "model": "SM-S928B",
        "device_name": "Galaxy S25 Ultra",
        "android_version": 35,
        "android_release": "15",
        "dpi": "640dpi",
        "resolution": "1440x3120",
        "cpu": "exynos2400",
        "chipset": "Exynos 2400",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-S926B",
        "device_name": "Galaxy S25+",
        "android_version": 35,
        "android_release": "15",
        "dpi": "480dpi",
        "resolution": "1440x3120",
        "cpu": "exynos2400",
        "chipset": "Exynos 2400",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-S921B",
        "device_name": "Galaxy S25",
        "android_version": 35,
        "android_release": "15",
        "dpi": "480dpi",
        "resolution": "1080x2340",
        "cpu": "exynos2400",
        "chipset": "Exynos 2400",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-S918B",
        "device_name": "Galaxy S24 Ultra",
        "android_version": 34,
        "android_release": "14",
        "dpi": "640dpi",
        "resolution": "1440x3120",
        "cpu": "s5e9945",
        "chipset": "Exynos 2400",
    },
    {
        "manufacturer": "Samsung",
        "model": "SM-F946B",
        "device_name": "Galaxy Z Fold5",
        "android_version": 34,
        "android_release": "14",
        "dpi": "420dpi",
        "resolution": "1812x2176",
        "cpu": "kalama",
        "chipset": "Snapdragon 8 Gen 2",
    },
    # ─── Google Pixel ───────────────────────────────
    {
        "manufacturer": "Google",
        "model": "Pixel 9 Pro",
        "device_name": "Pixel 9 Pro",
        "android_version": 35,
        "android_release": "15",
        "dpi": "560dpi",
        "resolution": "1280x2856",
        "cpu": "Tensor G4",
        "chipset": "Tensor G4",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 8 Pro",
        "device_name": "Pixel 8 Pro",
        "android_version": 34,
        "android_release": "14",
        "dpi": "560dpi",
        "resolution": "1344x2992",
        "cpu": "Tensor G3",
        "chipset": "Tensor G3",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 8",
        "device_name": "Pixel 8",
        "android_version": 34,
        "android_release": "14",
        "dpi": "420dpi",
        "resolution": "1080x2400",
        "cpu": "Tensor G3",
        "chipset": "Tensor G3",
    },
    # ─── Xiaomi ─────────────────────────────────────
    {
        "manufacturer": "Xiaomi",
        "model": "24129PN74G",
        "device_name": "Xiaomi 15 Pro",
        "android_version": 35,
        "android_release": "15",
        "dpi": "560dpi",
        "resolution": "1440x3200",
        "cpu": "sm8750",
        "chipset": "Snapdragon 8 Elite",
    },
    {
        "manufacturer": "Xiaomi",
        "model": "2311DRK48C",
        "device_name": "Xiaomi 14",
        "android_version": 34,
        "android_release": "14",
        "dpi": "480dpi",
        "resolution": "1200x2670",
        "cpu": "sm8650",
        "chipset": "Snapdragon 8 Gen 3",
    },
    # ─── OnePlus ────────────────────────────────────
    {
        "manufacturer": "OnePlus",
        "model": "CPH2583",
        "device_name": "OnePlus 12",
        "android_version": 34,
        "android_release": "14",
        "dpi": "480dpi",
        "resolution": "1440x3168",
        "cpu": "sm8650",
        "chipset": "Snapdragon 8 Gen 3",
    },
    {
        "manufacturer": "OnePlus",
        "model": "CPH2449",
        "device_name": "OnePlus 11",
        "android_version": 34,
        "android_release": "14",
        "dpi": "480dpi",
        "resolution": "1440x3216",
        "cpu": "kalama",
        "chipset": "Snapdragon 8 Gen 2",
    },
    # ─── OPPO ───────────────────────────────────────
    {
        "manufacturer": "OPPO",
        "model": "CPH2551",
        "device_name": "OPPO Find X7 Ultra",
        "android_version": 34,
        "android_release": "14",
        "dpi": "480dpi",
        "resolution": "1440x3168",
        "cpu": "sm8650",
        "chipset": "Snapdragon 8 Gen 3",
    },
    # ─── Sony ───────────────────────────────────────
    {
        "manufacturer": "Sony",
        "model": "XQ-DQ72",
        "device_name": "Xperia 1 VI",
        "android_version": 34,
        "android_release": "14",
        "dpi": "480dpi",
        "resolution": "1080x2340",
        "cpu": "sm8650",
        "chipset": "Snapdragon 8 Gen 3",
    },
    # ─── Nothing ────────────────────────────────────
    {
        "manufacturer": "Nothing",
        "model": "A065",
        "device_name": "Nothing Phone (2)",
        "android_version": 34,
        "android_release": "14",
        "dpi": "420dpi",
        "resolution": "1080x2412",
        "cpu": "sm8475",
        "chipset": "Snapdragon 8+ Gen 1",
    },
]

# ─── Instagram App versions (recent) ──────────────────────
IG_APP_VERSIONS = [
    "332.0.0.0.64",
    "331.0.0.0.93",
    "330.0.0.0.89",
    "329.0.0.0.45",
    "328.0.0.0.67",
    "327.0.0.0.50",
    "326.0.0.0.78",
]

# Language/locale pools
LOCALES = [
    "en_US", "en_GB", "uz_UZ", "ru_RU", "tr_TR",
    "de_DE", "fr_FR", "es_ES", "pt_BR", "it_IT",
    "ja_JP", "ko_KR", "ar_SA", "hi_IN", "id_ID",
]

# Carrier names
CARRIERS = [
    "wifi", "Beeline", "UMS", "Ucell", "MTS",
    "Megafon", "T-Mobile", "Verizon", "AT&T", "Vodafone",
    "O2", "Orange", "SFR", "Movistar", "TIM",
]


# ─── MAIN CLASS ──────────────────────────────────────────────

@dataclass
class DeviceFingerprint:
    """
    Complete Android device fingerprint.

    Every field is deterministic based on `seed` — same seed = same device.
    This is how FingerprintJS works: collect signals → hash → stable ID.

    Usage:
        fp = DeviceFingerprint.generate("my_unique_account_name")
        headers = fp.headers      # All X-IG-* headers
        ua = fp.user_agent        # Instagram app User-Agent
        fp.save("device.json")    # Persist to disk

        # Later:
        fp = DeviceFingerprint.load("device.json")
    """

    # ─── Device Info ──────────────
    manufacturer: str = ""
    model: str = ""
    device_name: str = ""
    android_version: int = 34
    android_release: str = "14"
    dpi: str = "480dpi"
    resolution: str = "1080x2400"
    cpu: str = ""
    chipset: str = ""

    # ─── Generated IDs (FingerprintJS-style: deterministic) ───
    device_id: str = ""          # android-[16 hex]
    phone_id: str = ""           # UUID
    client_uuid: str = ""        # UUID
    advertising_id: str = ""     # UUID
    waterfall_id: str = ""       # UUID
    family_device_id: str = ""   # UUID (Meta cross-app)

    # ─── Session ──────────────────
    ig_app_version: str = ""
    ig_app_version_code: str = ""
    locale: str = "en_US"
    carrier: str = "wifi"
    connection_type: str = "WIFI"
    timezone_offset: int = 0

    # ─── Metadata ─────────────────
    seed: str = ""
    created_at: float = 0.0

    # ═══════════════════════════════════════════════════════════
    # FACTORY METHODS
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def generate(
        cls,
        seed: str = "",
        device_index: Optional[int] = None,
        locale: str = "",
    ) -> "DeviceFingerprint":
        """
        Generate a complete device fingerprint.

        The CORE PRINCIPLE (from FingerprintJS):
        Same seed → Same fingerprint. Always. Deterministic.

        Args:
            seed: Unique identifier (username, account_id, etc.)
                  Empty = random (one-time use only)
            device_index: Force specific device from DB (0-14)
            locale: Force specific locale

        Returns:
            DeviceFingerprint with all fields populated
        """
        if not seed:
            seed = str(uuid.uuid4())

        # ─── Deterministic random from seed ───
        rng = random.Random(seed)

        # ─── Pick device from DB (deterministic) ───
        if device_index is not None:
            idx = device_index % len(DEVICE_DATABASE)
        else:
            idx = rng.randint(0, len(DEVICE_DATABASE) - 1)
        device = DEVICE_DATABASE[idx]

        # ─── Deterministic UUIDs (FingerprintJS hash approach) ───
        def make_uuid(component: str) -> str:
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{component}"))

        def make_android_id(component: str) -> str:
            raw = hashlib.md5(f"{seed}:{component}".encode()).hexdigest()
            return f"android-{raw[:16]}"

        # ─── App version (deterministic) ───
        app_ver = IG_APP_VERSIONS[rng.randint(0, len(IG_APP_VERSIONS) - 1)]
        app_code = str(rng.randint(520000000, 580000000))

        # ─── Locale & carrier ───
        fp_locale = locale or LOCALES[rng.randint(0, len(LOCALES) - 1)]
        fp_carrier = CARRIERS[rng.randint(0, len(CARRIERS) - 1)]

        # ─── Timezone ───
        tz_offsets = [-18000, -14400, -10800, 0, 3600, 7200, 10800, 14400, 18000, 19800, 32400]
        tz = tz_offsets[rng.randint(0, len(tz_offsets) - 1)]

        return cls(
            # Device
            manufacturer=device["manufacturer"],
            model=device["model"],
            device_name=device["device_name"],
            android_version=device["android_version"],
            android_release=device["android_release"],
            dpi=device["dpi"],
            resolution=device["resolution"],
            cpu=device["cpu"],
            chipset=device["chipset"],
            # IDs — deterministic from seed
            device_id=make_android_id("device"),
            phone_id=make_uuid("phone"),
            client_uuid=make_uuid("uuid"),
            advertising_id=make_uuid("adid"),
            waterfall_id=make_uuid("waterfall"),
            family_device_id=make_uuid("family"),
            # Session
            ig_app_version=app_ver,
            ig_app_version_code=app_code,
            locale=fp_locale,
            carrier=fp_carrier,
            connection_type="WIFI" if fp_carrier == "wifi" else "4G",
            timezone_offset=tz,
            # Meta
            seed=seed,
            created_at=time.time(),
        )

    # ═══════════════════════════════════════════════════════════
    # COMPUTED PROPERTIES
    # ═══════════════════════════════════════════════════════════

    @property
    def user_agent(self) -> str:
        """Instagram Android app User-Agent string."""
        return (
            f"Instagram {self.ig_app_version} "
            f"Android ({self.android_version}/{self.android_release}; "
            f"{self.dpi}; {self.resolution}; "
            f"{self.manufacturer}; {self.model}; "
            f"{self.model.lower().replace('-', '')}; {self.cpu}; "
            f"{self.locale}; {self.ig_app_version_code})"
        )

    @property
    def headers(self) -> Dict[str, str]:
        """
        Complete Instagram Private API headers.
        Like FingerprintJS — all signals are coherent.
        """
        now = time.time()
        return {
            "User-Agent": self.user_agent,
            "X-IG-App-ID": "567067343352427",
            "X-IG-Capabilities": "3brTv10=",
            "X-IG-Connection-Type": self.connection_type,
            "X-IG-Connection-Speed": f"{random.randint(1500, 4500)}kbps",
            "X-IG-Bandwidth-Speed-KBPS": f"{random.uniform(1000, 5000):.3f}",
            "X-IG-Bandwidth-TotalBytes-B": f"{random.randint(10000000, 99999999)}",
            "X-IG-Bandwidth-TotalTime-MS": f"{random.randint(500, 5000)}",
            "X-IG-EU-DC-ENABLED": "false",
            "X-IG-ABR-Connection-Speed-KBPS": f"{random.randint(1500, 5000)}",
            "X-IG-Device-ID": self.phone_id,
            "X-IG-Android-ID": self.device_id,
            "X-IG-Device-Locale": self.locale,
            "X-IG-App-Locale": self.locale,
            "X-IG-Mapped-Locale": self.locale,
            "X-IG-Timezone-Offset": str(self.timezone_offset),
            "X-Pigeon-Session-Id": f"UFS-{self.client_uuid}-0",
            "X-Pigeon-Rawclienttime": f"{now:.3f}",
            "X-FB-HTTP-Engine": "Liger",
            "X-FB-Client-IP": "True",
            "X-FB-Server-Cluster": "True",
            "X-Bloks-Is-Layout-RTL": "false",
            "X-Bloks-Is-Panorama-Enabled": "true",
            "X-IG-WWW-Claim": "0",
            "Accept-Language": self.locale.replace("_", "-"),
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Connection": "keep-alive",
        }

    @property
    def pigeon_session(self) -> str:
        """Pigeon session ID (analytics tracking)."""
        return f"UFS-{self.client_uuid}-0"

    @property
    def visitor_id(self) -> str:
        """
        FingerprintJS-style visitor ID.
        Deterministic hash of all device signals.
        """
        signals = (
            f"{self.device_id}|{self.phone_id}|{self.model}|"
            f"{self.manufacturer}|{self.android_version}|"
            f"{self.resolution}|{self.dpi}|{self.cpu}"
        )
        return hashlib.sha256(signals.encode()).hexdigest()[:32]

    @property
    def device_info(self) -> Dict[str, str]:
        """Device info summary for logging/debugging."""
        return {
            "device": f"{self.manufacturer} {self.device_name}",
            "model": self.model,
            "android": self.android_release,
            "app_version": self.ig_app_version,
            "device_id": self.device_id,
            "visitor_id": self.visitor_id,
            "locale": self.locale,
        }

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE — save/load
    # ═══════════════════════════════════════════════════════════

    def save(self, filepath: str = "device_fingerprint.json") -> None:
        """
        Save fingerprint to JSON file.
        Same seed can regenerate, but saving is faster + preserves created_at.
        """
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Device fingerprint saved: {filepath}")

    @classmethod
    def load(cls, filepath: str = "device_fingerprint.json") -> "DeviceFingerprint":
        """Load fingerprint from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Device fingerprint loaded: {filepath}")
        return cls(**data)

    @classmethod
    def load_or_generate(
        cls,
        filepath: str = "device_fingerprint.json",
        seed: str = "",
    ) -> "DeviceFingerprint":
        """
        Load existing or generate new fingerprint.
        Best practice: call this with a consistent seed per account.
        """
        if os.path.exists(filepath):
            return cls.load(filepath)
        fp = cls.generate(seed=seed)
        fp.save(filepath)
        return fp

    # ═══════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════

    def is_coherent(self) -> bool:
        """
        Verify all signals are coherent (FingerprintJS consistency check).
        Returns True if device specs match.
        """
        # Find device in DB
        for d in DEVICE_DATABASE:
            if d["model"] == self.model:
                return (
                    d["manufacturer"] == self.manufacturer
                    and d["android_version"] == self.android_version
                    and d["resolution"] == self.resolution
                    and d["dpi"] == self.dpi
                )
        # Custom device — can't verify
        return True

    @classmethod
    def list_devices(cls) -> List[Dict[str, str]]:
        """List all available devices in DB."""
        return [
            {
                "index": i,
                "name": d["device_name"],
                "model": d["model"],
                "android": d["android_release"],
                "manufacturer": d["manufacturer"],
            }
            for i, d in enumerate(DEVICE_DATABASE)
        ]

    def __repr__(self) -> str:
        return (
            f"DeviceFingerprint("
            f"{self.manufacturer} {self.device_name}, "
            f"Android {self.android_release}, "
            f"visitor_id={self.visitor_id[:12]}...)"
        )
