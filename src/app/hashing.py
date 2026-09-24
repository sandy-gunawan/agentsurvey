import io

from PIL import Image

HASH_SIZE = 8


def average_hash(data: bytes) -> str:
    img = Image.open(io.BytesIO(data)).convert("L").resize((HASH_SIZE, HASH_SIZE))
    pixels = list(img.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= mean else "0" for p in pixels)
    return f"{int(bits, 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def downscale(data: bytes, max_side: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()
