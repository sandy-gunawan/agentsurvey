import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import maps, rules, storage, vision
from .config import settings
from .hashing import average_hash, hamming

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Asisten Review Bukti Survei Rumah")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "aiConfigured": bool(settings.ai_endpoint and settings.ai_deployment),
        "mapsConfigured": settings.maps_enabled,
        "storageConfigured": settings.storage_enabled,
        "deployment": settings.ai_deployment,
    }


def _find_duplicates(case_id: str, hashes: list[dict]) -> list[dict]:
    index = storage.load_index()
    hits = []
    for entry in index:
        if entry.get("caseId") == case_id:
            continue
        for current in hashes:
            if hamming(entry["hash"], current["hash"]) <= settings.duplicate_threshold:
                hits.append(
                    {
                        "caseId": entry["caseId"],
                        "file": entry["file"],
                        "matchedWith": current["file"],
                    }
                )
    return hits


@app.post("/api/review")
async def review(
    caseId: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    claimedAddress: str = Form(""),
    requiredPhotos: str = Form(""),
    photos: list[UploadFile] = File(...),
) -> dict:
    if not settings.ai_endpoint or not settings.ai_deployment:
        raise HTTPException(500, "Endpoint atau deployment model belum dikonfigurasi.")

    loaded = [(p.filename or "tanpa-nama", await p.read()) for p in photos]
    hashes = [{"file": name, "hash": average_hash(data)} for name, data in loaded]

    required = [line.strip() for line in requiredPhotos.splitlines() if line.strip()]
    supplied = {name.lower() for name, _ in loaded}
    missing = [r for r in required if not any(r.lower() in s for s in supplied)]

    duplicates = _find_duplicates(caseId, hashes)

    location = {"mapCoverageLimited": True}
    if settings.maps_enabled:
        try:
            location = await maps.analyse_location(latitude, longitude, claimedAddress)
        except Exception as exc:  # layanan peta gagal tidak boleh menggagalkan seluruh proses
            location = {"error": str(exc), "mapCoverageLimited": True}

    findings = await asyncio.to_thread(
        vision.extract_findings, loaded, claimedAddress, location, required, missing
    )

    result = {
        "caseId": caseId,
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "modelDeployment": settings.ai_deployment,
        "evidence": {
            "photoCount": len(loaded),
            "photos": hashes,
            "coordinate": {"lat": latitude, "lon": longitude},
        },
        "buildingFindings": findings.get("buildingFindings", {}),
        "evidenceRefs": findings.get("evidenceRefs", {}),
        "photoQuality": findings.get("photoQuality", []),
        "observations": findings.get("observations", []),
        "locationFindings": location,
        "integrityFlags": {"similarPhotoCases": duplicates},
        "missingEvidence": missing,
        "cannotAssess": findings.get("cannotAssess", []),
        "notes": findings.get("notes", ""),
        "recommendation": rules.build_recommendation(
            missing, findings, location, duplicates
        ),
        "creditDecision": None,
        "propertyValue": None,
    }

    saved = [storage.save_photo(caseId, name, data) for name, data in loaded]
    saved.append(storage.append_index([{**h, "caseId": caseId} for h in hashes]))
    saved.append(storage.save_result(caseId, result))
    if not all(saved):
        result["storageWarning"] = "bukti tidak tersimpan permanen pada percobaan ini"

    return result
