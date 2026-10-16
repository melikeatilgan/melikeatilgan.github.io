"""Katalogdan statik site verisini üretir (GitHub Pages'te sunucusuz çalışır).

Çıktı (hedef/veri/):
  meta.json                 tarih, sayılar, kaynak notları
  ara/_dizin.json           arama parçalarının önek listesi
  ara/<önek>.json           [mpn, lcsc, üretici, kılıf, stok] satırları (gzip)
  p/<kova>.json             parça kayıtları (LCSC no // KOVA), muadilleri ile (gzip)

Dosyaların içeriği gzip ama uzantısı .json: indirme yöneticileri (ör. Internet Download Manager) .gz ve .bin
uzantılı istekleri yakalayıp sayfaya boş (204) yanıt bırakıyor. Arayüz gzip imzasına (1f 8b) bakıp açıyor; sunucu ayrıca sıkıştırırsa tarayıcı o katmanı kendisi açar.
"""
import gzip
import json
import re
import sys
import time
from collections import defaultdict
from itertools import islice
from pathlib import Path

from .eslestir import GUCLU_PIN, KURALLAR, PINSIZ, PinKaynagi, _deger, degerlendir
from .katalog import DB_YOLU, baglan

KOVA = 2000
ARA_SINIR = 3000
SINIF_SAYISI = {"dogrudan": 12, "farkli": 12, "kontrol": 12, "farkli_kilif": 6, "uygun_degil": 6}
DENEME = 250        # aynı kılıfta parça başına en çok değerlendirilen aday
DENEME_KILIF = 60   # farklı kılıfta
PIN_SATIR = ("dogrudan", "farkli", "kontrol", "uygun_degil")


def anahtar(mpn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", mpn.upper())


def _yaz(yol: Path, veri) -> int:
    yol.parent.mkdir(parents=True, exist_ok=True)
    ham = json.dumps(veri, ensure_ascii=False, separators=(",", ":")).encode()
    yol.write_bytes(gzip.compress(ham, 9))
    return yol.stat().st_size


def arama_dizini(satirlar: list, hedef: Path) -> int:
    """Önek ağacı: bir önekte ARA_SINIR'dan fazla satır varsa bir harf daha uzatılır."""
    def bol(onek: str, liste: list):
        if len(liste) <= ARA_SINIR or len(onek) >= 6:
            yield onek, liste
            return
        alt = defaultdict(list)
        for s in liste:
            alt[s[0][len(onek):len(onek) + 1] or "_"].append(s)
        for harf, l in alt.items():
            yield from bol(onek + harf, l)

    kok = defaultdict(list)
    for s in satirlar:
        k = anahtar(s[1])
        kok[(k[:2] or "_").ljust(2, "_")].append((k, *s))
    dizin = []
    for onek, liste in kok.items():
        for o, l in bol(onek, liste):
            l.sort(key=lambda x: (x[0], -x[5]))
            _yaz(hedef / "ara" / f"{o}.json", [[x[2], x[1], x[3], x[4], x[5]] for x in l])
            dizin.append(o)
    (hedef / "ara" / "_dizin.json").write_text(json.dumps(sorted(dizin)), encoding="utf-8")
    return len(dizin)


def _ozet(p: dict, sonuc: dict | None = None, pin_satiri: bool = False) -> dict:
    o = {"c": p["lcsc"], "m": p["mpn"], "u": p["uretici"], "k": p["kilif"], "f1": p["birim_fiyat"],
         "s": p["stok"], "sn": p["sinif"]}
    if sonuc:
        o.update({"n": sonuc["notlar"], "i": sonuc["ihlal"], "e": sonuc["eksik"], "b": sonuc["bilgi"]})
        pin = sonuc["pin"]
        if pin:
            o["pin"] = {"sonuc": pin["sonuc"], "guven": pin["guven"], "kaynak": [pin["eski"], pin["yeni"]]}
            if pin_satiri:
                o["pin"]["satir"] = [[s["no"], s["eski"], s["yeni"], s["durum"], s["aciklama"]] for s in pin["satirlar"]]
    return o


def grup_anahtari(p: dict) -> tuple:
    """Zorunlu 'eşit' kurallarının değerleri: yalnız bunlar tutan adaylar ayrıntılı incelenir."""
    k = []
    for kural in KURALLAR.get(p["aile"], []):
        if kural.tur == "esit" and kural.zorunlu and kural.uygulanir(p["alt"] or ""):
            v = _deger(p["ozl"], kural, p.get("ham"))  # degerlendir ile aynı okuma ("74HC Series" = "74HC")
            k.append(float(f"{v:.6g}") if isinstance(v, float) else v)  # round(v, 9) 100 pF'ı da 6,8 pF'ı da 0 yapıyordu
    return tuple(k)


def _sira(a: dict):
    """Önce pin tablosu olan, sonra stokta olan, sonra JLC temel/tercihli, sonra ucuz adaylar."""
    return (not a["pinli"], not a["stok"], a["sinif"] == "genis", a["birim_fiyat"] or 9e9)


def muadiller(p: dict, grup: dict, pk: PinKaynagi) -> dict:
    """grup: {"kilif": {kılıf: sıralı liste}, "tum": sıralı liste} (aynı alt kategori, aynı zorunlu değerler)."""
    siniflar = defaultdict(list)
    ayni = [a for a in grup["kilif"].get(p["kilif_k"], [])[:DENEME + 1] if a["lcsc"] != p["lcsc"]][:DENEME]
    diger = list(islice((a for a in grup["tum"] if a["kilif_k"] != p["kilif_k"]), DENEME_KILIF))
    for a in ayni + diger:
        s = degerlendir(p, a, pk)
        if len(siniflar[s["sinif"]]) < SINIF_SAYISI[s["sinif"]]:
            siniflar[s["sinif"]].append(_ozet(a, s, s["sinif"] in PIN_SATIR))
    return {"aday": len(grup["tum"]) - 1, "incelenen": len(ayni) + len(diger), **siniflar}


def disari_aktar(hedef: Path, db_yolu: Path = DB_YOLU) -> dict:
    bas = time.time()
    db = baglan(db_yolu)
    pk = PinKaynagi()
    sutun = ("lcsc", "mpn", "uretici", "ust", "alt", "aile", "kilif", "kilif_k", "aciklama", "datasheet",
             "url", "gorsel", "fiyat", "birim_fiyat", "stok", "sinif", "ozellik", "ozellik_ham")
    parcalar = [dict(zip(sutun, r)) for r in db.execute(f"SELECT {','.join(sutun)} FROM parca")]
    for p in parcalar:
        p["ozl"] = json.loads(p.pop("ozellik"))
        p["ham"] = json.loads(p["ozellik_ham"])
        p["pinli"] = bool(p["aile"] in KURALLAR and p["aile"] not in PINSIZ
                          and pk.bul(p["lcsc"], p["mpn"], p["kilif_k"], p["aile"], p["uretici"])["guven"] in GUCLU_PIN)

    n_ara = arama_dizini([(p["lcsc"], p["mpn"], p["uretici"], p["kilif"], p["stok"]) for p in parcalar], hedef)

    gruplar = defaultdict(lambda: {"kilif": defaultdict(list), "tum": []})
    for p in parcalar:
        if p["aile"] in KURALLAR:
            g = gruplar[(p["alt"], grup_anahtari(p))]
            g["kilif"][p["kilif_k"]].append(p)
            g["tum"].append(p)
    for g in gruplar.values():
        g["tum"].sort(key=_sira)
        for liste in g["kilif"].values():
            liste.sort(key=_sira)

    kovalar = defaultdict(list)
    sayac = defaultdict(int)
    pin_tablolu = 0
    for i, p in enumerate(parcalar):
        kayit = {"c": p["lcsc"], "m": p["mpn"], "u": p["uretici"], "ust": p["ust"], "alt": p["alt"], "a": p["aile"],
                 "k": p["kilif"], "d": p["aciklama"], "ds": p["datasheet"], "url": p["url"], "g": p["gorsel"],
                 "f": json.loads(p["fiyat"]), "s": p["stok"], "sn": p["sinif"], "o": p["ham"]}
        if p["aile"] not in PINSIZ:
            pin = pk.bul(p["lcsc"], p["mpn"], p["kilif_k"], p["aile"], p["uretici"])
            if pin["pinler"]:
                kayit["p"] = {k: pin[k] for k in ("kaynak", "guven", "kicad", "kicad_ds", "pinler", "kicad_pinler") if pin.get(k)}
                pin_tablolu += 1
        if p["aile"] in KURALLAR:
            kayit["mu"] = muadiller(p, gruplar[(p["alt"], grup_anahtari(p))], pk)
            for sinif in SINIF_SAYISI:
                sayac[sinif] += bool(kayit["mu"].get(sinif))
        kovalar[int(p["lcsc"][1:]) // KOVA].append(kayit)
        if i % 50000 == 0:
            print(f"{i}/{len(parcalar)} ({time.time() - bas:.0f} sn)", flush=True)

    boyut = sum(_yaz(hedef / "p" / f"{k}.json", v) for k, v in kovalar.items())
    bilgi = dict(db.execute("SELECT anahtar, deger FROM bilgi").fetchall())
    meta = {"uretim": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tarama": int(bilgi.get("tarama_zamani", 0)),
            "parca": len(parcalar), "kova": KOVA, "ara_parca": n_ara,
            "aile": {a: sum(1 for p in parcalar if p["aile"] == a) for a in KURALLAR},
            "muadilli": dict(sayac), "pinli": sum(p["pinli"] for p in parcalar), "pin_tablolu": pin_tablolu, "boyut_mb": round(boyut / 1e6, 1)}
    (hedef / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    kurallar = {a: [{"etiket": k.etiket, "ozellik": k.ozellik, "tur": "belirsiz" if k.belirsiz else k.tur,
                     "zorunlu": k.zorunlu} for k in ks]
                for a, ks in KURALLAR.items()}
    (hedef / "kurallar.json").write_text(json.dumps(kurallar, ensure_ascii=False), encoding="utf-8")
    print(f"bitti: {time.time() - bas:.0f} sn", meta, flush=True)
    return meta


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    disari_aktar(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "site" / "muadil" / "veri")
