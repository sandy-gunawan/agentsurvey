import base64
import json
from pathlib import Path

from openai import AzureOpenAI

from .auth import get_cognitive_token_provider
from .config import settings
from .hashing import downscale

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system_prompt.txt").read_text(
    encoding="utf-8"
)


def _client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.ai_endpoint,
        azure_ad_token_provider=get_cognitive_token_provider(),
        api_version=settings.ai_api_version,
    )


def _image_part(data: bytes) -> dict:
    encoded = base64.b64encode(downscale(data)).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"},
    }


def extract_findings(
    photos: list[tuple[str, bytes]],
    claimed_address: str,
    map_result: dict,
    required_photos: list[str],
    missing_photos: list[str],
) -> dict:
    context = {
        "alamatPengajuan": claimed_address,
        "hasilPemeriksaanPeta": map_result,
        "daftarFotoWajib": required_photos,
        "fotoWajibBelumAda": missing_photos,
        "namaBerkasTerlampir": [name for name, _ in photos],
    }

    content: list[dict] = [
        {
            "type": "text",
            "text": "Data pendukung:\n" + json.dumps(context, ensure_ascii=False, indent=2),
        }
    ]
    for name, data in photos:
        content.append({"type": "text", "text": f"Berkas berikut: {name}"})
        content.append(_image_part(data))

    completion = _client().chat.completions.create(
        model=settings.ai_deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model mengembalikan JSON tidak sah: {raw[:200]}") from exc
