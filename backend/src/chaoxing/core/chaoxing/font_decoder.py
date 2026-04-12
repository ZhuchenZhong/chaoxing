"""Font decoder for Chaoxing obfuscated text.

Ported from ``bak/legacy-cli/api/cxsecret_font.py`` and
``bak/legacy-cli/api/font_decoder.py``.  The module decodes text that
Chaoxing renders with a custom TTF font whose glyph shapes are shuffled.
It works by hashing each glyph in the page-specific font and looking up
the hash in a pre-computed reference table (``font_map_table.json``).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Union

from bs4 import BeautifulSoup

try:
    from fontTools.ttLib.tables._g_l_y_f import Glyph, table__g_l_y_f
    from fontTools.ttLib.ttFont import TTFont

    FONTTOOLS_AVAILABLE = True
except ImportError:  # pragma: no cover
    FONTTOOLS_AVAILABLE = False

# Kangxi radical → standard character replacement table
KX_RADICALS_TAB = str.maketrans(
    "⼀⼁⼂⼃⼄⼅⼆⼇⼈⼉⼊⼋⼌⼍⼎⼏⼐⼑⼒⼓⼔⼕⼖⼗⼘⼙⼚⼛⼜⼝⼞⼟⼠⼡⼢⼣⼤⼥⼦⼧⼨⼩⼪⼫⼬⼭⼮⼯⼰⼱⼲⼳⼴⼵⼶⼷⼸⼹⼺⼻⼼⼽⼾⼿⽀⽁⽂⽃⽄⽅⽆⽇⽈⽉⽊⽋⽌⽍⽎⽏⽐⽑⽒⽓⽔⽕⽖⽗⽘⽙⽚⽛⽜⽝⽞⽟⽠⽡⽢⽣⽤⽥⽦⽧⽨⽩⽪⽫⽬⽭⽮⽯⽰⽱⽲⽳⽴⽵⽶⽷⽸⽹⽺⽻⽼⽽⽾⽿⾀⾁⾂⾃⾄⾅⾆⾇⾈⾉⾊⾋⾌⾍⾎⾏⾐⾑⾒⾓⾔⾕⾖⾗⾘⾙⾚⾛⾜⾝⾞⾟⾠⾡⾢⾣⾤⾥⾦⾧⾨⾩⾪⾫⾬⾭⾮⾯⾰⾱⾲⾳⾴⾵⾶⾷⾸⾹⾺⾻⾼髙⾽⾾⾿⿀⿁⿂⿃⿄⿅⿆⿇⿈⿉⿊⿋⿌⿍⿎⿏⿐⿑⿒⿓⿔⿕⺠⻬⻩⻢⻜⻅⺟⻓",
    "一丨丶丿乙亅二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾見角言谷豆豕豸貝赤走足身車辛辰辵邑酉采里金長門阜隶隹雨青非面革韋韭音頁風飛食首香馬骨高高髟鬥鬯鬲鬼魚鳥鹵鹿麥麻黃黍黑黹黽鼎鼓鼠鼻齊齒龍龜龠民齐黄马飞见母长",
)

_RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
FONT_BASE64_PATTERN = r"base64,([\w\W]+?)\'"
FONT_DATA_URL_PREFIX = "data:application/font-ttf;charset=utf-8;base64,"


class FontDecodeError(Exception):
    """Raised when font decoding fails."""


class FontHashDAO:
    """Pre-computed glyph-hash → unicode mapping loaded from JSON."""

    def __init__(self, file_path: str | Path | None = None) -> None:
        self.char_map: Dict[str, str] = {}  # unicode name → hash
        self.hash_map: Dict[str, str] = {}  # hash → unicode name

        if file_path is None:
            file_path = _RESOURCES_DIR / "font_map_table.json"
        else:
            file_path = Path(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                self.char_map = json.load(fp)
                self.hash_map = {h: c for c, h in self.char_map.items()}
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise FontDecodeError(f"Failed to load font map: {file_path} — {exc}") from exc

    def find_char(self, font_hash: str) -> Optional[str]:
        return self.hash_map.get(font_hash)

    def find_hash(self, char: str) -> Optional[str]:
        return self.char_map.get(char)


# Module-level singleton; gracefully degrade if font map is missing
try:
    _fonthash_dao = FontHashDAO()
except Exception:
    _fonthash_dao = FontHashDAO.__new__(FontHashDAO)
    _fonthash_dao.char_map = {}
    _fonthash_dao.hash_map = {}


def _hash_glyph(glyph: Any) -> str:
    """Compute MD5 hash of a TTF glyph's coordinate data."""
    if glyph.numberOfContours <= 0:
        return ""
    pos_data: list[str] = []
    last_index = 0
    for i in range(glyph.numberOfContours):
        end_point = glyph.endPtsOfContours[i]
        for j in range(last_index, end_point + 1):
            x, y = glyph.coordinates[j]
            flag = glyph.flags[j] & 0x01
            pos_data.append(f"{x}{y}{flag}")
        last_index = end_point + 1
    return hashlib.md5("".join(pos_data).encode()).hexdigest()


def font2map(font_data: Union[BytesIO, Path, str]) -> Dict[str, str]:
    """Extract glyph-name → hash mapping from a TTF font."""
    if not FONTTOOLS_AVAILABLE:
        raise FontDecodeError("fonttools is not installed")

    font_hashmap: Dict[str, str] = {}

    if isinstance(font_data, str) and font_data.startswith(FONT_DATA_URL_PREFIX):
        try:
            font_data = BytesIO(base64.b64decode(font_data[len(FONT_DATA_URL_PREFIX) :]))
        except Exception as exc:
            raise FontDecodeError(f"Cannot decode base64 font data: {exc}") from exc

    try:
        with TTFont(font_data, lazy=False) as font_file:
            table: table__g_l_y_f = font_file["glyf"]
            for name in table.glyphOrder:
                if name.startswith("uni"):
                    gh = _hash_glyph(table.glyphs[name])
                    if gh:
                        font_hashmap[name] = gh
    except Exception as exc:
        raise FontDecodeError(f"Cannot parse font file: {exc}") from exc

    return font_hashmap


def decrypt(dst_fontmap: Dict[str, str], encrypted_text: str) -> str:
    """Decrypt Chaoxing obfuscated text using a page-specific font map."""
    result: list[str] = []
    for char in encrypted_text:
        char_code = f"uni{ord(char):X}"
        if char_code in dst_fontmap:
            dst_hash = dst_fontmap[char_code]
            original = _fonthash_dao.find_char(dst_hash)
            if original:
                try:
                    result.append(chr(int(original[3:], 16)))
                    continue
                except (ValueError, IndexError):
                    pass
        result.append(char)
    return "".join(result).translate(KX_RADICALS_TAB)


class FontDecoder:
    """High-level decoder: extracts a font from HTML and decrypts text."""

    def __init__(self, html_content: Optional[str] = None) -> None:
        self.html_content = html_content
        self._font_map: Optional[Dict[str, str]] = None
        if html_content:
            self._init_font_map(html_content)

    def _init_font_map(self, html_content: str) -> None:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            style_tag = soup.find("style", id="cxSecretStyle")
            if not style_tag or not style_tag.text:
                raise FontDecodeError("No cxSecretStyle style tag found")

            match = re.search(FONT_BASE64_PATTERN, style_tag.text)
            if not match:
                raise FontDecodeError("Cannot extract font data from style tag")

            font_base64 = match.group(1)
            font_data_url = FONT_DATA_URL_PREFIX + font_base64
            self._font_map = font2map(font_data_url)
        except FontDecodeError:
            self._font_map = None
        except Exception:
            self._font_map = None

    def decode(self, target_str: str) -> str:
        if not self._font_map:
            raise FontDecodeError("Font map not initialised")
        return decrypt(self._font_map, target_str)

    def set_html_content(self, html_content: str) -> None:
        self.html_content = html_content
        self._init_font_map(html_content)
