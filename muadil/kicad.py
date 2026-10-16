"""KiCad sembol kütüphanesinden pin tablosu çıkarır.

KiCad'in resmî kütüphanesi kütüphane ekibinin denetiminden geçer (KLC kuralları); bu yüzden
birinci pin kaynağı olarak kullanılır. Lisans: CC-BY-SA 4.0 (atıf sitede ve README'de).

Çıktı: {sembol_adi: {"lib", "fp", "filtre", "ds", "pinler": {no: [ad, elektriksel_tip, birim]}}}
"ds" sembolün datasheet adresidir; hangi üreticinin dizilimini gösterdiğini anlamak için kullanılır.
Birim 0 tüm birimlerde ortak demektir; çok birimli sembollerde (ör. TL072) birim = kanal.
"""
import gzip
import json
import re
import sys
from pathlib import Path

VARSAYILAN = Path("C:/Program Files/KiCad/10.0/share/kicad/symbols")
CIKTI = Path(__file__).resolve().parent.parent / "kaynak" / "kicad_pinler.json.gz"

UST = re.compile(r'^\t\(symbol "([^"]+)"', re.M)
ALT = re.compile(r'^\t\t\(symbol "([^"]+)_(\d+)_(\d+)"', re.M)
PIN = re.compile(r'\(pin (\w+) \w+.*?\(name "((?:[^"\\]|\\.)*)".*?\(number "([^"]*)"', re.S)


def _ozellik(blok: str, ad: str) -> str:
    m = re.search(r'\(property "' + re.escape(ad) + r'" "((?:[^"\\]|\\.)*)"', blok)
    return m.group(1) if m else ""


def _pinler(blok: str) -> dict:
    pinler = {}
    konumlar = [(m.start(), int(m.group(2))) for m in ALT.finditer(blok)] + [(len(blok), 0)]
    for (bas, birim), (son, _) in zip(konumlar, konumlar[1:]):
        for m in PIN.finditer(blok, bas, son):
            pinler.setdefault(m.group(3), [m.group(2), m.group(1), birim])
    return pinler


def oku(dizin: Path = VARSAYILAN) -> dict:
    tum = {}
    for dosya in sorted(dizin.glob("*.kicad_sym")):
        metin = dosya.read_text(encoding="utf-8")
        bas = [m.start() for m in UST.finditer(metin)] + [len(metin)]
        for a, b in zip(bas, bas[1:]):
            blok = metin[a:b]
            ad = UST.match(blok).group(1)
            ust = re.search(r'^\t\t\(extends "([^"]+)"', blok, re.M)
            tum[ad] = {
                "lib": dosya.stem,
                "ust": ust.group(1) if ust else None,
                "fp": _ozellik(blok, "Footprint"),
                "filtre": _ozellik(blok, "ki_fp_filters"),
                "ds": _ozellik(blok, "Datasheet"),
                "pinler": _pinler(blok),
            }
    for kayit in tum.values():  # türetilmiş semboller pinleri üstten alır
        ust = kayit.pop("ust")
        while ust and not kayit["pinler"]:
            kayit["pinler"] = tum[ust]["pinler"]
            kayit["fp"] = kayit["fp"] or tum[ust]["fp"]
            kayit["filtre"] = kayit["filtre"] or tum[ust]["filtre"]
            kayit["ds"] = kayit["ds"] or tum[ust]["ds"]
            ust = None
    return {ad: k for ad, k in tum.items() if k["pinler"]}


if __name__ == "__main__":
    dizin = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN
    veri = oku(dizin)
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(CIKTI, "wt", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print(len(veri), "sembol ->", CIKTI)
