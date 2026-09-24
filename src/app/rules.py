def build_recommendation(
    missing_photos: list[str],
    findings: dict,
    location: dict,
    duplicates: list[dict],
) -> dict:
    reasons: list[str] = []

    if missing_photos:
        reasons.append(f"foto wajib belum ada: {', '.join(missing_photos)}")

    building = findings.get("buildingFindings", {}) or {}
    unknown = [k for k, v in building.items() if v == "tidak_dapat_dinilai"]
    if building and len(unknown) > len(building) / 2:
        reasons.append("sebagian besar bidang tidak dapat dinilai dari bukti")

    quality_issues = [
        q.get("file")
        for q in findings.get("photoQuality", []) or []
        if q.get("issue") not in (None, "tidak_ada_masalah")
    ]
    if quality_issues:
        reasons.append(f"mutu foto perlu diperbaiki: {', '.join(filter(None, quality_issues))}")

    needs_visit: list[str] = []

    if location.get("addressMatch") == "tidak_cocok":
        needs_visit.append("alamat hasil peta tidak cocok dengan alamat pengajuan")
    if duplicates:
        cases = ", ".join(sorted({d["caseId"] for d in duplicates}))
        needs_visit.append(f"terdapat foto serupa pada berkas lain: {cases}")
    if location.get("mapCoverageLimited"):
        needs_visit.append("data jalan di sekitar lokasi tidak memadai")
    if building.get("forSaleSign") == "ada":
        needs_visit.append("terdapat papan dijual atau dikontrakkan pada foto")

    if needs_visit:
        return {"action": "perlu_kunjungan", "reasons": needs_visit + reasons}
    if reasons:
        return {"action": "perlu_bukti_tambahan", "reasons": reasons}
    return {"action": "lengkap", "reasons": ["bukti wajib terpenuhi dan tidak ada penanda"]}
