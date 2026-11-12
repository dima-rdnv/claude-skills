"""Decode an Unreal MCP CaptureViewport/CaptureEditorImage result (JSON with base64 PNG) to an image file.

Usage: python decode_capture.py <tool-result.txt> <out.png> [max_width]
"""
import base64
import io
import json
import re
import sys


def main():
    src, out = sys.argv[1], sys.argv[2]
    max_w = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
    text = open(src, encoding="utf-8").read()
    try:
        data = json.loads(text)
        while isinstance(data, list):
            data = data[0]
        if "text" in data:
            data = json.loads(data["text"])
        rv = data.get("returnValue", data)
        b64 = rv["image"]["data"] if "image" in rv else rv["data"]
    except Exception:
        b64 = max(re.findall(r'"data"\s*:\s*"([A-Za-z0-9+/=]+)"', text), key=len)
    raw = base64.b64decode(b64)
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        if img.width > max_w:
            img = img.resize((max_w, round(img.height * max_w / img.width)), Image.LANCZOS)
        img.save(out, quality=88)
        print(out, img.size)
    except ImportError:
        open(out, "wb").write(raw)
        print(out, len(raw), "bytes (PIL missing, not resized)")


if __name__ == "__main__":
    main()
