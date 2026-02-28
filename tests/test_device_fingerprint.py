"""
Tests for DeviceFingerprint — Android device emulation.
"""

import json
import os
import tempfile
import pytest

from instaharvest_v2.device_fingerprint import (
    DeviceFingerprint,
    DEVICE_DATABASE,
    IG_APP_VERSIONS,
)


class TestDeviceFingerprintGenerate:
    """Test fingerprint generation."""

    def test_generate_default(self):
        fp = DeviceFingerprint.generate("test_seed")
        assert fp.manufacturer != ""
        assert fp.model != ""
        assert fp.device_id.startswith("android-")
        assert fp.phone_id != ""
        assert fp.client_uuid != ""
        assert fp.seed == "test_seed"

    def test_deterministic(self):
        """Same seed must produce same fingerprint — FingerprintJS principle."""
        fp1 = DeviceFingerprint.generate("stable_seed")
        fp2 = DeviceFingerprint.generate("stable_seed")
        assert fp1.device_id == fp2.device_id
        assert fp1.phone_id == fp2.phone_id
        assert fp1.client_uuid == fp2.client_uuid
        assert fp1.model == fp2.model
        assert fp1.visitor_id == fp2.visitor_id

    def test_different_seeds_different_fp(self):
        fp1 = DeviceFingerprint.generate("account_1")
        fp2 = DeviceFingerprint.generate("account_2")
        assert fp1.device_id != fp2.device_id
        assert fp1.phone_id != fp2.phone_id
        assert fp1.visitor_id != fp2.visitor_id

    def test_device_index(self):
        fp = DeviceFingerprint.generate("test", device_index=0)
        assert fp.manufacturer == "Samsung"
        assert fp.model == "SM-S928B"  # Galaxy S25 Ultra

    def test_custom_locale(self):
        fp = DeviceFingerprint.generate("test", locale="uz_UZ")
        assert fp.locale == "uz_UZ"

    def test_random_seed(self):
        """Empty seed generates random fingerprint."""
        fp1 = DeviceFingerprint.generate()
        fp2 = DeviceFingerprint.generate()
        assert fp1.device_id != fp2.device_id


class TestDeviceFingerprintProperties:
    """Test computed properties."""

    def test_user_agent_format(self):
        fp = DeviceFingerprint.generate("test", device_index=0)
        ua = fp.user_agent
        assert "Instagram" in ua
        assert "Android" in ua
        assert "Samsung" in ua
        assert "SM-S928B" in ua

    def test_headers_keys(self):
        fp = DeviceFingerprint.generate("test")
        headers = fp.headers
        assert "User-Agent" in headers
        assert "X-IG-App-ID" in headers
        assert "X-IG-Device-ID" in headers
        assert "X-IG-Android-ID" in headers
        assert "X-IG-Connection-Type" in headers
        assert "X-Pigeon-Session-Id" in headers
        assert "X-FB-HTTP-Engine" in headers

    def test_headers_values(self):
        fp = DeviceFingerprint.generate("test")
        headers = fp.headers
        assert headers["X-IG-App-ID"] == "567067343352427"
        assert headers["X-FB-HTTP-Engine"] == "Liger"
        assert headers["X-IG-Android-ID"] == fp.device_id

    def test_visitor_id(self):
        fp = DeviceFingerprint.generate("test")
        vid = fp.visitor_id
        assert len(vid) == 32
        assert all(c in "0123456789abcdef" for c in vid)

    def test_pigeon_session(self):
        fp = DeviceFingerprint.generate("test")
        assert fp.pigeon_session.startswith("UFS-")

    def test_device_info(self):
        fp = DeviceFingerprint.generate("test")
        info = fp.device_info
        assert "device" in info
        assert "model" in info
        assert "visitor_id" in info

    def test_coherent(self):
        fp = DeviceFingerprint.generate("test")
        assert fp.is_coherent() is True


class TestDeviceFingerprintPersistence:
    """Test save/load."""

    def test_save_load(self):
        fp = DeviceFingerprint.generate("persist_test")
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            path = f.name

        try:
            fp.save(path)
            loaded = DeviceFingerprint.load(path)
            assert loaded.device_id == fp.device_id
            assert loaded.phone_id == fp.phone_id
            assert loaded.model == fp.model
            assert loaded.visitor_id == fp.visitor_id
        finally:
            os.unlink(path)

    def test_load_or_generate_new(self):
        path = tempfile.mktemp(suffix=".json")
        try:
            fp = DeviceFingerprint.load_or_generate(path, seed="new_test")
            assert os.path.exists(path)
            assert fp.seed == "new_test"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_or_generate_existing(self):
        path = tempfile.mktemp(suffix=".json")
        try:
            fp1 = DeviceFingerprint.load_or_generate(path, seed="existing")
            fp2 = DeviceFingerprint.load_or_generate(path, seed="different_seed")
            # Should load existing, not generate new
            assert fp2.device_id == fp1.device_id
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestDeviceDatabase:
    """Test device database."""

    def test_database_not_empty(self):
        assert len(DEVICE_DATABASE) >= 10

    def test_all_devices_have_required_fields(self):
        required = ["manufacturer", "model", "android_version", "dpi", "resolution", "cpu"]
        for d in DEVICE_DATABASE:
            for key in required:
                assert key in d, f"Missing {key} in {d.get('device_name', '?')}"

    def test_list_devices(self):
        devices = DeviceFingerprint.list_devices()
        assert len(devices) == len(DEVICE_DATABASE)
        assert "name" in devices[0]
        assert "model" in devices[0]

    def test_app_versions_valid(self):
        for v in IG_APP_VERSIONS:
            parts = v.split(".")
            assert len(parts) >= 3


class TestDeviceFingerprintRepr:
    """Test repr."""

    def test_repr(self):
        fp = DeviceFingerprint.generate("test", device_index=0)
        r = repr(fp)
        assert "Samsung" in r
        assert "Galaxy S25 Ultra" in r
        assert "visitor_id=" in r
