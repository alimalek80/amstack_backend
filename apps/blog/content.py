"""Post body format: a rich text document as produced by the Tiptap editor (ProseMirror JSON).

    {"type": "doc", "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Setup"}]},
        {"type": "paragraph", "content": [
            {"type": "text", "text": "Run ", "marks": []},
            {"type": "text", "text": "pip install", "marks": [{"type": "code"}]}]},
        {"type": "codeBlock", "attrs": {"language": "bash"}, "content": [{"type": "text", "text": "..."}]}]}

Only the node types, marks and attributes listed below are kept; everything else is rejected,
so the stored document can be rendered safely without ever trusting raw HTML.
"""
import re

from rest_framework import serializers

LANGUAGE_RE = re.compile(r"^[a-z0-9+#.-]{0,30}$")
SAFE_SRC_RE = re.compile(r"^(/media/|https://)")
SAFE_HREF_RE = re.compile(r"^(https?://|mailto:|/(?!/)|#)", re.IGNORECASE)

NODES = {
    "doc", "paragraph", "text", "heading", "bulletList", "orderedList", "listItem",
    "blockquote", "codeBlock", "horizontalRule", "hardBreak", "image",
    "table", "tableRow", "tableHeader", "tableCell",
}
MARKS = {"bold", "italic", "underline", "strike", "code", "highlight", "link"}
MAX_DEPTH = 40
MAX_NODES = 20_000
MAX_TEXT = 300_000


def _span(value):
    return value if isinstance(value, int) and 0 < value <= 50 else 1


def empty_doc():
    return {"type": "doc", "content": []}


class _Cleaner:
    def __init__(self):
        self.nodes = 0
        self.chars = 0

    def fail(self, message):
        raise serializers.ValidationError(message)

    def text_attr(self, value, limit=500):
        return value[:limit] if isinstance(value, str) else ""

    def mark(self, raw):
        if not isinstance(raw, dict) or raw.get("type") not in MARKS:
            self.fail("The post contains formatting that is not supported.")
        mark = {"type": raw["type"]}
        if raw["type"] == "link":
            href = (raw.get("attrs") or {}).get("href")
            if not isinstance(href, str) or not SAFE_HREF_RE.match(href.strip()):
                self.fail(f"Link “{href}” is not allowed. Use an http(s), mailto or relative link.")
            mark["attrs"] = {"href": href.strip()[:2000]}
        return mark

    def attrs(self, kind, raw):
        raw = raw if isinstance(raw, dict) else {}
        if kind == "heading":
            level = raw.get("level")
            return {"level": level if level in (1, 2, 3, 4, 5, 6) else 2}
        if kind == "orderedList":
            start = raw.get("start")
            return {"start": start if isinstance(start, int) and 0 < start < 100_000 else 1}
        if kind == "codeBlock":
            language = raw.get("language") or ""
            language = language.strip().lower() if isinstance(language, str) else ""
            return {"language": language if LANGUAGE_RE.match(language) else ""}
        if kind in ("tableCell", "tableHeader"):
            return {"colspan": _span(raw.get("colspan")), "rowspan": _span(raw.get("rowspan"))}
        if kind == "image":
            src = raw.get("src")
            if not isinstance(src, str) or not SAFE_SRC_RE.match(src):
                self.fail("Images must be uploaded here or use an https:// link.")
            return {"src": src[:1000], "alt": self.text_attr(raw.get("alt")), "title": self.text_attr(raw.get("title"))}
        return None

    def node(self, raw, depth):
        if depth > MAX_DEPTH:
            self.fail("The post is nested too deeply.")
        if not isinstance(raw, dict) or raw.get("type") not in NODES:
            self.fail("The post contains a block type that is not supported.")
        self.nodes += 1
        if self.nodes > MAX_NODES:
            self.fail("The post is too long.")

        kind = raw["type"]
        node = {"type": kind}
        if kind == "text":
            text = raw.get("text")
            if not isinstance(text, str) or not text:
                self.fail("The post contains an empty text node.")
            self.chars += len(text)
            if self.chars > MAX_TEXT:
                self.fail("The post is too long.")
            node["text"] = text
            marks = raw.get("marks") or []
            if marks:
                node["marks"] = [self.mark(m) for m in marks]
            return node

        attrs = self.attrs(kind, raw.get("attrs"))
        if attrs is not None:
            node["attrs"] = attrs
        content = raw.get("content") or []
        if not isinstance(content, list):
            self.fail("The post content is malformed.")
        if content:
            node["content"] = [self.node(child, depth + 1) for child in content]
        return node


def clean_doc(value):
    if value in (None, [], {}):
        return empty_doc()
    if not isinstance(value, dict) or value.get("type") != "doc":
        raise serializers.ValidationError("Body must be a rich text document.")
    return _Cleaner().node(value, 0)


def plain_text(node):
    """All text in a document, used for reading time."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    return " ".join(plain_text(child) for child in node.get("content") or [])
