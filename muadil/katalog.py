"""Taranan JLC verisinden katalog veritabanını kurar ve parça arar.

Girdi: veri/ham/jlc/*.jsonl.gz (muadil.jlc tara). Çıktı: veri/katalog.db (SQLite).
Ham özellikler ("1.1V@(800mA)") jlcparts'ın normalleştiricisiyle birimli sayılara çevrilir.
"""
import gzip
import json
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

from jlcparts import datatables

# jlcparts çok değerli alanlarda ("83%、87%") ekrana uyarı basıyor; o alanlar ham kalır.
datatables.print = lambda *a, **k: None

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "veri" / "ham" / "jlc"
DB_YOLU = KOK / "veri" / "katalog.db"

SEMA = """
CREATE TABLE parca(
    lcsc TEXT PRIMARY KEY, mpn TEXT NOT NULL, uretici TEXT, ust TEXT, alt TEXT, aile TEXT,
    kilif TEXT, kilif_k TEXT, aciklama TEXT, datasheet TEXT, url TEXT, gorsel TEXT,
    fiyat TEXT, birim_fiyat REAL, stok INTEGER, sinif TEXT, ozellik TEXT, ozellik_ham TEXT);
CREATE INDEX parca_mpn ON parca(mpn COLLATE NOCASE);
CREATE INDEX parca_grup ON parca(alt, kilif_k);
CREATE VIRTUAL TABLE mpn_ara USING fts5(mpn, content='parca', content_rowid='rowid', tokenize='trigram');
CREATE TABLE bilgi(anahtar TEXT PRIMARY KEY, deger TEXT);
"""


def aile(ust: str, alt: str) -> str:
    """Pin rolü çözümlemesi ve muadil kuralları için parça ailesi."""
    a = alt.lower()
    if "low drop out" in a or "linear voltage regulator" in a or a.startswith("voltage regulators - linear"):
        return "regulator"
    if "555" in a:
        return "zamanlayici"
    if ust == "Amplifiers/Comparators" and ("amplifier" in a or "comparator" in a or "opamp" in a) \
            and "audio" not in a and "current sense" not in a:
        return "opamp"
    if ust == "Transistors/Thyristors" and ("mosfet" in a or "bipolar" in a or "bjt" in a or "digital transistor" in a):
        return "transistor"
    if ust == "Diodes" or "tvs" in a or "zener" in a:
        return "diyot"
    if ust == "Logic":
        return "lojik"
    if ust == "Resistors" and "chip resistor" in a:
        return "direnc"
    if ust == "Capacitors" and "mlcc" in a:
        return "mlcc"
    return "genel"


# JLC'deki kılıf adlarının eşanlamlıları -> ortak ad. Kural: aynı ortak ad = aynı lehim izi ailesi.
KILIF_ES = [
    (r"^(SOT-?23|SOT-?23-?3L?|TO-?236(AB)?|SOT-?23\(TO-?236\))$", "SOT-23-3"),
    (r"^(SOT-?23-?5L?|SOT-?25|SOT-?753|SC-?74A)$", "SOT-23-5"),
    (r"^(SOT-?23-?6L?|SOT-?26|SC-?74)$", "SOT-23-6"),
    (r"^(SOIC-?8|SOP-?8|SO-?8|SOP-?8-?150MIL|SOIC-?8-?150MIL|SOP-?8L)$", "SOIC-8"),
    (r"^(SOIC-?14|SOP-?14|SO-?14|SOP-?14-?150MIL)$", "SOIC-14"),
    (r"^(SOIC-?16|SOP-?16|SO-?16|SOP-?16-?150MIL)$", "SOIC-16"),
    (r"^(TO-?220|TO-?220-?3L?|TO-?220AB)$", "TO-220-3"),
    (r"^(SOT-?223|SOT-?223-?3L?|SOT-?223-?4)$", "SOT-223"),
    (r"^(TO-?252|TO-?252-?2L?|TO-?252-?3|DPAK|TO-?252AA)$", "TO-252"),
    (r"^(TO-?263|TO-?263-?[23]L?|D2PAK|TO-?263AB)$", "TO-263"),
    (r"^(SOT-?89|SOT-?89-?3L?)$", "SOT-89-3"),
    (r"^(SMA|DO-?214AC|SMA\(DO-?214AC\))$", "SMA"),
    (r"^(SMB|DO-?214AA|SMB\(DO-?214AA\))$", "SMB"),
    (r"^(SMC|DO-?214AB|SMC\(DO-?214AB\))$", "SMC"),
    (r"^(SOD-?123|SOD-?123F?L?)$", "SOD-123"),
    (r"^(SOD-?323|SC-?76)$", "SOD-323"),
    (r"^(SOT-?323|SC-?70|SC-?70-?3)$", "SOT-323"),
    (r"^(TO-?92|TO-?92-?3L?)$", "TO-92"),
    (r"^(DIP-?8|PDIP-?8)$", "DIP-8"),
]


def kilif_k(kilif: str | None) -> str:
    k = (kilif or "").upper().replace(" ", "").replace("_", "-")
    for desen, ad in KILIF_ES:
        if re.match(desen, k):
            return ad
    return k


def _normal(ozellikler: list) -> tuple[dict, dict]:
    ham, normal = {}, {}
    for o in ozellikler or []:
        ad, deger = o.get("attribute_name_en"), o.get("attribute_value_name")
        if not ad or deger in (None, "", "-"):
            continue
        ham[ad] = deger
        n = _normallestir(ad, deger)
        if n:
            normal[n[0]] = n[1]
    return ham, normal


@lru_cache(maxsize=None)
def _normallestir(ad: str, deger: str):
    try:
        yeni_ad, n = datatables.normalizeAttribute(ad, deger)
        return yeni_ad, n["values"]
    except Exception:  # noqa: BLE001 - tanınmayan özellik ham haliyle kalır
        return None


def satir(r: dict) -> tuple:
    ham, normal = _normal(r.get("attributes"))
    fiyat = [[p["startNumber"], p["productPrice"]] for p in r.get("componentPrices") or []]
    sinif = "temel" if r.get("componentLibraryType") == "base" else \
        "tercihli" if r.get("preferredComponentFlag") else "genis"
    ust, alt = r.get("secondSortName") or "", r.get("firstSortName") or ""
    return (r["componentCode"], r["componentModelEn"], r.get("componentBrandEn"), ust, alt, aile(ust, alt),
            r.get("componentSpecificationEn"), kilif_k(r.get("componentSpecificationEn")), r.get("describe"),
            r.get("dataManualUrl"), r.get("lcscGoodsUrl"), r.get("minImage"), json.dumps(fiyat),
            fiyat[0][1] if fiyat else None, r.get("stockCount") or 0, sinif,
            json.dumps(normal, ensure_ascii=False), json.dumps(ham, ensure_ascii=False))


def kur(ham: Path = HAM, db_yolu: Path = DB_YOLU) -> dict:
    """Katalogu baştan kurar; yeni dosyaya yazıp sonunda yerine koyar (yarım veri bırakmaz)."""
    gecici = db_yolu.with_suffix(".yeni")
    gecici.unlink(missing_ok=True)
    db = sqlite3.connect(gecici)
    db.executescript(SEMA)
    for dosya in sorted(ham.glob("*.jsonl.gz")):
        with gzip.open(dosya, "rt", encoding="utf-8") as f:
            db.executemany("INSERT OR REPLACE INTO parca VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (satir(json.loads(s)) for s in f))
    db.execute("INSERT INTO mpn_ara(mpn_ara) VALUES ('rebuild')")
    toplam = db.execute("SELECT count(*) FROM parca").fetchone()[0]
    tarih = max((p.stat().st_mtime for p in ham.glob("*.jsonl.gz")), default=0)
    db.executemany("INSERT INTO bilgi VALUES (?,?)", [("parca_sayisi", str(toplam)), ("tarama_zamani", str(int(tarih)))])
    db.commit()
    db.close()
    gecici.replace(db_yolu)
    return {"parca": toplam}


def baglan(db_yolu: Path = DB_YOLU) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{db_yolu}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


LCSC_KODU = re.compile(r"^[Cc]\d+$")


def bul(db: sqlite3.Connection, sorgu: str, sinir: int = 20) -> dict:
    """Birebir eşleşmeyi ve yakın adayları ayrı döndürür; birini ötekine çevirmez."""
    s = sorgu.strip()
    if not s:
        return {"birebir": [], "yakin": []}
    if LCSC_KODU.match(s):
        birebir = db.execute("SELECT * FROM parca WHERE lcsc = ?", (s.upper(),)).fetchall()
    else:
        birebir = db.execute("SELECT * FROM parca WHERE mpn = ? COLLATE NOCASE ORDER BY stok DESC", (s,)).fetchall()
    yakin = []
    if len(s) >= 3:
        yakin = db.execute(
            "SELECT p.* FROM mpn_ara JOIN parca p ON p.rowid = mpn_ara.rowid WHERE mpn_ara MATCH ? "
            "ORDER BY length(p.mpn), p.stok DESC LIMIT ?", ('"' + s.replace('"', '""') + '"', sinir + len(birebir))).fetchall()
        tam = {r["lcsc"] for r in birebir}
        yakin = [r for r in yakin if r["lcsc"] not in tam][:sinir]
    return {"birebir": birebir, "yakin": yakin}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(kur())
