from __future__ import annotations

import base64

import pyaes

AES_KEY = "u2oh6Vu^HWe4_AES"


def _pkcs7_padding(payload: bytes, block_size: int = 16) -> bytes:
    pad_size = block_size - len(payload) % block_size
    return payload + (chr(pad_size).encode() * pad_size)


def _split_blocks(payload: bytes, block_size: int = 16) -> list[bytes]:
    return [payload[index : index + block_size] for index in range(0, len(payload), block_size)]


class AESCipher:
    def __init__(self, key: str = AES_KEY) -> None:
        key_bytes = key.encode("utf-8")
        self.key = key_bytes
        self.iv = key_bytes

    def encrypt(self, plaintext: str) -> str:
        cbc = pyaes.AESModeOfOperationCBC(self.key, self.iv)
        ciphertext = b""
        for block in _split_blocks(_pkcs7_padding(plaintext.encode("utf-8"))):
            ciphertext += cbc.encrypt(block)
        return base64.b64encode(ciphertext).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        cbc = pyaes.AESModeOfOperationCBC(self.key, self.iv)
        plaintext = b""
        for block in _split_blocks(base64.b64decode(ciphertext)):
            plaintext += cbc.decrypt(block)
        pad_size = plaintext[-1]
        return plaintext[:-pad_size].decode("utf-8")
