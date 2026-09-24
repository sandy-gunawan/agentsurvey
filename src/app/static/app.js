const form = document.getElementById("form");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const submitBtn = document.getElementById("submit");

const LABELS = {
  floors: "Jumlah lantai",
  buildingType: "Jenis bangunan",
  wallMaterial: "Material dinding",
  roofMaterial: "Material atap",
  carPark: "Tempat parkir mobil",
  roadSurface: "Permukaan jalan",
  houseNumberText: "Nomor rumah",
  fence: "Pagar",
  forSaleSign: "Papan dijual",
  reverseGeocodedAddress: "Alamat hasil peta",
  nearestStreet: "Jalan terdekat",
  onMainRoad: "Di jalan utama",
  addressMatch: "Kecocokan alamat",
  addressDistanceMeter: "Selisih ke alamat pengajuan (m)",
  snapDistanceMeter: "Selisih ke jalan kendaraan (m)",
  carAccessible: "Terjangkau mobil",
  mapCoverageLimited: "Cakupan peta terbatas",
};

const RECO_TEXT = {
  lengkap: "Bukti lengkap",
  perlu_bukti_tambahan: "Perlu bukti tambahan",
  perlu_kunjungan: "Perlu kunjungan",
};

function fillTable(el, data, refs = {}) {
  el.innerHTML = "";
  Object.entries(data || {}).forEach(([key, value]) => {
    if (key === "roadUse" || key === "error") return;
    const row = el.insertRow();
    row.insertCell().textContent = LABELS[key] || key;
    const cell = row.insertCell();
    cell.textContent = value === null || value === "" ? "—" : String(value);
    if (refs[key]?.length) {
      const ref = document.createElement("span");
      ref.className = "ref";
      ref.textContent = `sumber: ${refs[key].join(", ")}`;
      cell.appendChild(ref);
    }
  });
}

function fillList(el, items) {
  el.innerHTML = items?.length
    ? items.map((i) => `<li>${typeof i === "string" ? i : JSON.stringify(i)}</li>`).join("")
    : "<li>—</li>";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  resultEl.hidden = true;
  statusEl.textContent = "Memproses bukti…";

  try {
    const response = await fetch("/api/review", {
      method: "POST",
      body: new FormData(form),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();

    const reco = document.getElementById("recommendation");
    reco.className = `reco ${data.recommendation.action}`;
    reco.innerHTML =
      `<div>${RECO_TEXT[data.recommendation.action] || data.recommendation.action}</div>` +
      `<ul>${data.recommendation.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>`;

    fillTable(document.getElementById("findings"), data.buildingFindings, data.evidenceRefs);
    fillTable(document.getElementById("location"), data.locationFindings);

    const flags = [
      ...data.missingEvidence.map((m) => `Foto wajib belum ada: ${m}`),
      ...data.integrityFlags.similarPhotoCases.map(
        (d) => `Foto ${d.matchedWith} mirip dengan ${d.file} pada berkas ${d.caseId}`
      ),
      ...(data.photoQuality || [])
        .filter((q) => q.issue && q.issue !== "tidak_ada_masalah")
        .map((q) => `Mutu foto ${q.file}: ${q.issue}`),
    ];
    fillList(document.getElementById("flags"), flags);
    fillList(document.getElementById("cannot"), data.cannotAssess);

    const thumbs = document.getElementById("thumbs");
    thumbs.innerHTML = "";
    Array.from(document.getElementById("photos").files).forEach((file) => {
      const figure = document.createElement("figure");
      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      const caption = document.createElement("figcaption");
      caption.textContent = file.name;
      figure.append(img, caption);
      thumbs.appendChild(figure);
    });

    document.getElementById("raw").textContent = JSON.stringify(data, null, 2);
    statusEl.textContent = `Selesai. ${data.evidence.photoCount} foto diproses.`;
    resultEl.hidden = false;
  } catch (error) {
    statusEl.textContent = `Gagal: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
  }
});
