"""Tests for AES encryption/decryption and video enc formula."""

from __future__ import annotations

import hashlib

from chaoxing.core.chaoxing.crypto import AESCipher, AES_KEY
from chaoxing.core.services.video_service import _generate_enc


# ---------------------------------------------------------------------------
# AESCipher round-trip
# ---------------------------------------------------------------------------


def test_aes_cipher_encrypt_decrypt_round_trip():
    cipher = AESCipher()
    plaintext = "hello-world-1234"
    encrypted = cipher.encrypt(plaintext)
    # Encrypted should not equal plaintext
    assert encrypted != plaintext
    # Decryption should recover original
    assert cipher.decrypt(encrypted) == plaintext


def test_aes_cipher_unicode_round_trip():
    cipher = AESCipher()
    plaintext = "用户密码测试_中文字符"
    encrypted = cipher.encrypt(plaintext)
    assert cipher.decrypt(encrypted) == plaintext


def test_aes_cipher_deterministic():
    """Same plaintext + key always produces same ciphertext."""
    cipher = AESCipher()
    plain = "deterministic-test"
    assert cipher.encrypt(plain) == cipher.encrypt(plain)


def test_aes_cipher_custom_key():
    key = "1234567890abcdef"  # exactly 16 bytes
    cipher = AESCipher(key=key)
    encrypted = cipher.encrypt("test")
    assert cipher.decrypt(encrypted) == "test"

    # Different key should produce different ciphertext
    default_cipher = AESCipher()
    assert default_cipher.encrypt("test") != encrypted


def test_aes_cipher_empty_string():
    cipher = AESCipher()
    encrypted = cipher.encrypt("")
    assert cipher.decrypt(encrypted) == ""


def test_aes_cipher_long_string():
    cipher = AESCipher()
    plaintext = "A" * 1000
    encrypted = cipher.encrypt(plaintext)
    assert cipher.decrypt(encrypted) == plaintext


# ---------------------------------------------------------------------------
# Video enc formula — critical for Chaoxing progress logging
# ---------------------------------------------------------------------------


def test_generate_enc_matches_expected_hash():
    """Verify enc formula matches legacy get_enc behavior."""
    result = _generate_enc(
        clazz_id="2001",
        userid="42",
        jobid="job-1",
        object_id="obj-1",
        playing_time=60,
        duration=300,
    )
    # Reconstruct expected hash manually
    raw = "[2001][42][job-1][obj-1][60000][d_yHJ!$pdA~5][300000][0_300]"
    expected = hashlib.md5(raw.encode()).hexdigest()
    assert result == expected


def test_generate_enc_varies_with_playing_time():
    enc_a = _generate_enc("c1", "u1", "j1", "o1", 0, 100)
    enc_b = _generate_enc("c1", "u1", "j1", "o1", 50, 100)
    enc_c = _generate_enc("c1", "u1", "j1", "o1", 100, 100)
    assert enc_a != enc_b != enc_c


def test_generate_enc_varies_with_duration():
    enc_a = _generate_enc("c1", "u1", "j1", "o1", 60, 100)
    enc_b = _generate_enc("c1", "u1", "j1", "o1", 60, 200)
    assert enc_a != enc_b


def test_generate_enc_zero_playing_time():
    result = _generate_enc("c1", "u1", "j1", "o1", 0, 300)
    raw = "[c1][u1][j1][o1][0][d_yHJ!$pdA~5][300000][0_300]"
    expected = hashlib.md5(raw.encode()).hexdigest()
    assert result == expected


def test_generate_enc_special_chars_in_ids():
    """Ensure special characters in IDs are included verbatim."""
    result = _generate_enc("c-1", "u@2", "j#3", "o&4", 10, 50)
    raw = "[c-1][u@2][j#3][o&4][10000][d_yHJ!$pdA~5][50000][0_50]"
    expected = hashlib.md5(raw.encode()).hexdigest()
    assert result == expected
