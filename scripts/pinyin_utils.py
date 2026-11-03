"""Pinyin helpers shared by the data scripts (syllable split/count, sentence segmentation)."""
import re

TONED = "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ"
VOW = "aeiouüv" + TONED
PLAIN = "aeiouüv"
_SYL = re.compile(
    rf"(?:zh|ch|sh|[bpmfdtnlgkhjqxrzcsyw])?(?=[{VOW}])[{PLAIN}]*[{TONED}]?[{PLAIN}]*"
    rf"(?:ng(?![{VOW}])|n(?![{VOW}])|r(?![{VOW}]))?",
    re.I,
)
CJK = re.compile(r"[㐀-鿿豈-﫿]")


def syllables(p: str) -> list:
    """Split a pinyin string ('xuéshēng', 'yí xià') into syllables."""
    out = []
    for part in re.split(r"[\s'’\-]+", p.strip()):
        out += _SYL.findall(part)
    return out


def nsyl(p: str) -> int:
    return len(syllables(p))


def expected_syllables(word: str) -> int:
    return len([c for c in word if CJK.match(c)])


def pinyin_fits(word: str, py: str) -> bool:
    """Syllable count matches the characters (兒 may be erhua: 這兒 zhèr, 一點兒 yìdiǎnr)."""
    n, k = nsyl(py), expected_syllables(word)
    return n == k or (len(word) > 1 and "兒" in word and py.rstrip().endswith("r") and n == k - word.count("兒"))


PUNCT = set("，。？！、；：「」『』（）…—,.?!;: \"“”‘’《》〈〉·")


def segment(sentence: str, pydict: dict, maxlen: int = None):
    """Greedy longest-match segmentation -> [[token, pinyin], ...] and list of unknown chars."""
    if maxlen is None:
        maxlen = max(map(len, pydict)) if pydict else 1
    out, miss, i = [], [], 0
    while i < len(sentence):
        ch = sentence[i]
        if not CJK.match(ch):
            out.append([ch, ""]); i += 1; continue
        for L in range(min(maxlen, len(sentence) - i), 0, -1):
            t = sentence[i:i + L]
            if t in pydict:
                out.append([t, pydict[t]]); i += L; break
        else:
            out.append([ch, ""]); miss.append(ch); i += 1
    return out, miss


def tokens_to_py(tokens) -> str:
    """Pinyin line shown in the sheet: one item per Chinese token, separated by spaces."""
    return " ".join(p if p else "?" for t, p in tokens if CJK.match(t[0]))


def apply_py_line(tokens, line: str):
    """Put the editor's pinyin line back onto the tokens. Returns None if the count does not match."""
    parts = line.split()
    cjk_idx = [i for i, (t, _) in enumerate(tokens) if CJK.match(t[0])]
    if len(parts) != len(cjk_idx):
        return None
    out = [list(t) for t in tokens]
    for i, p in zip(cjk_idx, parts):
        out[i][1] = "" if p == "?" else p
    return out
