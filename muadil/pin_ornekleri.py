"""Ana sayfadaki "Aynı kılıf, farklı bacak" kutusunun verisini üretir: site/pin/.

dizin.json: seçilmiş örnekler ve kılıf havuzlarının listesi. <n>.json: bir KiCad ayak izini kullanan
bütün sembollerin farklı dizilimleri (sayfa her seferinde bir havuzdan rastgele parçalar çeker).
Pin adları elle yazılmaz; KiCad 10 sembol kütüphanesinden (kaynak/kicad_pinler.json.gz) ve
UMW örneği için LCSC/EasyEDA önbelleğinden (kaynak/easyeda.jsonl) okunur. Seçilmiş örneklerde iki şey
denetlenir: parçalar aynı ayak izini kullanıyor mu, dizilimler gerçekten farklı mı.
Kullanım: python -m muadil.pin_ornekleri
"""
import fnmatch
import gzip
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KICAD = json.load(gzip.open(KOK / "kaynak/kicad_pinler.json.gz", "rt", encoding="utf-8"))
EASYEDA = {json.loads(s)["lcsc"]: json.loads(s) for s in open(KOK / "kaynak/easyeda.jsonl", encoding="utf-8") if s.strip()}

SOT23 = ["Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-23-3"]
# (kılıf, tür, çizim, kabul edilen KiCad ayak izleri, [(gösterilecek ad, sembol), ...])
# Çizim: sot23 sot223 sot89 to92 to220 sot23-5 sot23-6 cift-N dort-N bga
ORNEKLER = [
    ("SOT-23", "Lineer regülatör (LDO)", "sot23", SOT23, [("XC6206", "XC6206PxxxMR"), ("AP7381", "AP7381-33SA-7"), ("LM3480", "LM3480-3.3")]),
    ("TO-92", "NPN transistör", "to92", ["Package_TO_SOT_THT:TO-92_Inline"], [("BC547", "BC547"), ("2N3904", "2N3904"), ("2SC1815", "2SC1815")]),
    ("SOT-223", "Lineer regülatör (LDO)", "sot223", ["Package_TO_SOT_SMD:SOT-223-3_TabPin2"], [("AMS1117-3.3", "AMS1117-3.3"), ("AP7361C", "AP7361C-33E"), ("MCP1804", "MCP1804x-3302xDB")]),
    ("TO-220", "Gerilim regülatörü", "to220", ["Package_TO_SOT_THT:TO-220-3_Vertical"], [("LM7805", "LM7805_TO220"), ("LM7905", "LM7905_TO220"), ("LM317", "LM317_TO-220")]),
    ("TO-92", "Küçük gerilim regülatörü", "to92", ["Package_TO_SOT_THT:TO-92_Inline"], [("L78L05", "L78L05_TO92"), ("L79L05", "L79L05_TO92"), ("LM317L", "LM317L_TO92")]),
    ("SOT-23", "FET", "sot23", SOT23, [("2N7002", "2N7002"), ("MMBF4393", "MMBF4393"), ("BF545A", "BF545A")]),
    ("TO-92", "FET", "to92", ["Package_TO_SOT_THT:TO-92_Inline"], [("2N7000", "2N7000"), ("BS170", "BS170"), ("BF245A", "BF245A")]),
    ("SOT-89", "Gerilim regülatörü", "sot89", ["Package_TO_SOT_SMD:SOT-89-3"], [("L78L05", "L78L05_SOT89"), ("L79L05", "L79L05_SOT89"), ("AP2204R-3.3", "AP2204R-3.3")]),
    ("SOT-23-5", "LDO, şarj entegresi, lojik kapı", "sot23-5", ["Package_TO_SOT_SMD:SOT-23-5"],
     [("AP2112K", "AP2112K-3.3"), ("LP2985", "LP2985-3.3"), ("MCP73831", "MCP73831-2-OT"), ("74LVC1G04", "74LVC1G04")]),
    ("SOT-23-6", "ESD koruma, DC-DC, pil koruma, MCU", "sot23-6", ["Package_TO_SOT_SMD:SOT-23-6"],
     [("USBLC6-2SC6", "USBLC6-2SC6"), ("MT3608", "MT3608"), ("DW01A", "DW01A"), ("ATtiny10", "ATtiny10-TS")]),
    ("SOIC-8 (3,9 mm)", "Zamanlayıcı, RS-485, EEPROM, opamp", "cift-8", ["Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"],
     [("NE555", "NE555D"), ("MAX485", "MAX485E"), ("24C02", "24C02Cx-x-SN"), ("LM358", "LM358")]),
    ("SOIC-8 (5,3 mm)", "Flash bellek, mikrodenetleyici, RTC", "cift-8", ["Package_SO:SOIC-8_5.3x5.3mm_P1.27mm"],
     [("W25Q32JV", "W25Q32JVSS"), ("ATtiny85", "ATtiny85-20S"), ("DS1302", "DS1302S+")]),
    ("DIP-8", "Zamanlayıcı, MCU, optokuplör, RTC", "cift-8", ["Package_DIP:DIP-8_W7.62mm"],
     [("NE555", "NE555P"), ("ATtiny85", "ATtiny85-20P"), ("6N137", "6N137"), ("DS1307", "DS1307+")]),
    ("SOIC-16 (3,9 mm)", "USB-UART dönüştürücü, ADC", "cift-16", ["Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"],
     [("CH340G", "CH340G"), ("CH340C", "CH340C"), ("HX711", "HX711")]),
    ("SOIC-16 / DIP-16", "Kaydırma yazmacı, çoklayıcı, sürücü, RS-232", "cift-16", ["Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"],
     [("74HC595", "74HC595"), ("CD4051B", "CD4051B"), ("ULN2003A", "ULN2003A"), ("MAX232", "MAX232")]),
    # Çok bacaklı kılıflar: iki parça, farklı pinler renklenir.
    ("LQFP-48", "STM32 mikrodenetleyici", "dort-48", ["Package_QFP:LQFP-48_7x7mm_P0.5mm"], [("STM32F103C8", "STM32F103C8Tx"), ("STM32F030C8", "STM32F030C8Tx")]),
    ("LQFP-48", "STM32 mikrodenetleyici", "dort-48", ["Package_QFP:LQFP-48_7x7mm_P0.5mm"], [("STM32F103C8", "STM32F103C8Tx"), ("STM32G030C8", "STM32G030C8Tx")]),
    ("LQFP-64", "STM32 mikrodenetleyici", "dort-64", ["Package_QFP:LQFP-64_10x10mm_P0.5mm"], [("STM32F103RB", "STM32F103RBTx"), ("STM32F030R8", "STM32F030R8Tx")]),
    ("TSSOP-20", "STM32 mikrodenetleyici", "cift-20", ["Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm"], [("STM32F030F4", "STM32F030F4Px"), ("STM32G030F6", "STM32G030F6Px")]),
    ("TSSOP-20", "8 bit ve RISC-V mikrodenetleyici", "cift-20", ["Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm"], [("STM8S003F3", "STM8S003F3P"), ("CH32V003F4", "CH32V003FxPx")]),
    ("TQFP-32", "AVR ve ARM mikrodenetleyici", "dort-32", ["Package_QFP:TQFP-32_7x7mm_P0.8mm"], [("ATmega328P", "ATmega328P-A"), ("ATSAMD21E18", "ATSAMD21E18A-A")]),
    ("QFN-48 (7×7 mm)", "STM32 mikrodenetleyici", "dort-48", ["Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm"], [("STM32F401CC", "STM32F401CCUx"), ("STM32F411CE", "STM32F411CEUx")]),
    ("QFN-48 (7×7 mm)", "STM32 mikrodenetleyici", "dort-48", ["Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm"], [("STM32F401CC", "STM32F401CCUx"), ("STM32G431CB", "STM32G431CBUx")]),
    ("QFN-32 (5×5 mm)", "Wi-Fi SoC ve FPGA", "dort-32", ["Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.7x3.7mm"], [("ESP32-C3", "ESP32-C3"), ("iCE40LP384", "ICE40LP384-SG32")]),
    ("QFN-56 (7×7 mm)", "Wi-Fi SoC", "dort-56", ["Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm"], [("ESP32-S2", "ESP32-S2"), ("ESP32-S3", "ESP32-S3")]),
    ("UFBGA-64", "Microchip ve ST mikrodenetleyici", "bga", ["Package_BGA:UFBGA-64_5x5mm_Layout8x8_P0.5mm"], [("ATSAMD21J15", "ATSAMD21J15B-C"), ("STM32F072RB", "STM32F072RBHx")]),
    ("FBGA-96", "DDR3L ve DDR4 bellek", "bga", ["Package_BGA:Micron_FBGA-96_7.5x13.5mm_Layout9x16_P0.8mm"], [("DDR3L MT41K256M16", "MT41K256M16LY"), ("DDR4 MT40A512M16", "MT40A512M16LY")]),
    ("TFBGA-216", "STM32 mikrodenetleyici", "bga", ["Package_BGA:TFBGA-216_13x13mm_Layout15x15_P0.8mm"], [("STM32F429NE", "STM32F429NEHx"), ("STM32F746NE", "STM32F746NEHx")]),
]

SATIR = "ABCDEFGHJKLMNPRTUVWY"  # JEDEC top satırları (I, O, Q, S, X, Z yok)


def temiz(ad):
    """KiCad biçimlemesini sadeleştirir: ~{RST} -> /RST, V_{SSQ} -> VSSQ."""
    return re.sub(r"[_^]\{([^}]*)\}", r"\1", re.sub(r"~\{([^}]*)\}", r"/\1", ad))


def pin_adi(ad, tur, birim, coklu=True):
    """Çok birimli opamp sembollerinde adsız çıkış ve +/- girişler birim harfiyle adlandırılır (OUTA, IN-A)."""
    if coklu and ad in ("", "~", "+", "-"):
        ad = {"+": "IN+", "-": "IN-"}.get(ad, "OUT" if tur == "output" else ad) + chr(64 + birim)
    return temiz(ad)


def ayak_izi_uygun(sembol, kabul):
    v = KICAD[sembol]
    if v["fp"]:
        return v["fp"] in kabul
    ad = kabul[0].split(":")[1]  # kılıfı sabit olmayan genel sembol: filtresi bu ayak izini kapsamalı
    return any(fnmatch.fnmatch(ad, f) for f in v["filtre"].split())


def sira(pinler, cizim):
    if cizim == "bga":
        def k(n):
            m = re.fullmatch(r"([A-Z]+)(\d+)", n)
            return (len(m[1]), SATIR.index(m[1][-1]), int(m[2]))
        return sorted(pinler, key=k)
    # cift-8, dort-48, sot23-5: sayı adda; diğer sabit çizimler üç bacaklı. Termal ped (EP) dahil edilmez.
    say = int(cizim.split("-")[1]) if "-" in cizim else 3
    return [str(i) for i in range(1, say + 1)]


def cizim_turu(fp):
    """KiCad ayak izi adından sayfadaki çizim türü; çizilemeyen kılıf için None."""
    ad = fp.split(":")[-1]
    if re.fullmatch(r"SOT-23(-3)?", ad):
        return "sot23"
    if m := re.fullmatch(r"SOT-23-([56])", ad):
        return "sot23-" + m[1]
    sabit = {"SOT-223-3_TabPin2": "sot223", "SOT-89-3": "sot89", "TO-92_Inline": "to92", "TO-220-3_Vertical": "to220"}
    if ad in sabit:
        return sabit[ad]
    if m := re.match(r"(?:SOIC|SOP|TSSOP|SSOP|MSOP|DIP|HTSSOP|VSSOP|QSOP)-(\d+)", ad):
        return f"cift-{m[1]}"
    govde = re.search(r"_(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", ad)
    if (m := re.match(r"[A-Z]*(?:QFP|QFN)-(\d+)", ad)) and int(m[1]) % 4 == 0 and govde and govde[1] == govde[2]:
        return f"dort-{m[1]}"  # kare gövde: her kenarda eşit bacak
    if "BGA" in ad:
        return "bga"
    return None


def etiket(fp):
    """("QFN-48", "7×7 mm · 0,5 mm adım · EP 5,6×5,6") gibi kısa ad ve ayrıntı."""
    ad = fp.split(":")[-1]
    kisa = re.sub(r"-1EP$", "", ad.split("_")[0])
    kisa = {"SOT-23-3": "SOT-23", "SOT-223-3": "SOT-223", "SOT-89-3": "SOT-89", "TO-220-3": "TO-220"}.get(kisa, kisa)
    ayrinti = []
    if g := re.search(r"_(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", ad):
        ayrinti.append(f"{g[1]}×{g[2]} mm")
    if a := re.search(r"_P(\d+(?:\.\d+)?)mm", ad):
        ayrinti.append(f"{a[1]} mm adım")
    if e := re.search(r"_EP(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", ad):
        ayrinti.append(f"EP {e[1]}×{e[2]}")
    return kisa, " · ".join(ayrinti).replace(".", ",")


TOP = re.compile(r"[A-Z]+\d+")


def havuzlar(en_az_sembol=12, en_az_dizilim=3):
    """Her ayak izi için onu kullanan sembolleri dizilimlerine göre gruplar."""
    gruplar = defaultdict(dict)
    for ad, v in KICAD.items():
        c = v["fp"] and cizim_turu(v["fp"])
        if not c:
            continue
        p = v["pinler"]
        if c == "bga" and not all(TOP.fullmatch(n) for n in p):
            continue
        dizi = sira(p, c)
        if not all(n in p for n in dizi):
            continue
        coklu = max(x[2] for x in p.values()) > 1
        adlar = tuple(pin_adi(*p[n], coklu) for n in dizi)
        if not all(adlar):
            continue
        gruplar[(v["fp"], tuple(dizi) if c == "bga" else None)].setdefault(adlar, []).append(ad)
    cikti = []
    for (fp, toplar), desen in gruplar.items():
        sembol = sum(len(a) for a in desen.values())
        if len(desen) < en_az_dizilim or sembol < en_az_sembol:
            continue
        kisa, ayrinti = etiket(fp)
        h = {"kilif": kisa, "ayrinti": ayrinti, "cizim": cizim_turu(fp), "sembol": sembol, "dizilim": len(desen),
             "desenler": [{"pin": list(k), "adlar": sorted(a)} for k, a in desen.items()]}
        if toplar:
            h["toplar"] = list(toplar)
        cikti.append(h)
    return sorted(cikti, key=lambda h: -h["sembol"])


def main():
    cikti = []
    for kilif, tur, cizim, kabul, parcalar in ORNEKLER:
        for _, s in parcalar:
            assert ayak_izi_uygun(s, kabul), (s, KICAD[s]["fp"] or KICAD[s]["filtre"], kabul)
        dizi = sira(KICAD[parcalar[0][1]]["pinler"], cizim)
        satir = []
        for ad, s in parcalar:
            p = KICAD[s]["pinler"]
            assert all(n in p for n in dizi), (s, [n for n in dizi if n not in p][:5])
            satir.append({"ad": ad, "pin": [pin_adi(*p[n]) for n in dizi]})
        assert len({tuple(p["pin"]) for p in satir}) == len(satir), (kilif, tur)  # hepsi farklı dizilim
        o = {"kilif": kilif, "tur": tur, "cizim": cizim, "parcalar": satir, "kaynak": "KiCad 10 sembol kütüphanesi"}
        if cizim == "bga":
            o["toplar"] = dizi
        cikti.append(o)
    umw = [temiz(EASYEDA["C347376"]["pinler"][n][0]) for n in ("1", "2", "3")]
    torex = [temiz(KICAD["XC6206PxxxMR"]["pinler"][n][0]) for n in ("1", "2", "3")]
    assert torex != umw
    cikti.append({"kilif": "SOT-23", "tur": "Aynı parça numarası, iki üretici", "cizim": "sot23",
                  "parcalar": [{"ad": "Torex XC6206P332MR", "pin": torex}, {"ad": "UMW XC6206P332MR", "pin": umw}],
                  "kaynak": "KiCad 10 (Torex) ve LCSC/EasyEDA sembolü C347376 (UMW)"})
    hedef = KOK / "site/pin"
    shutil.rmtree(hedef, ignore_errors=True)
    hedef.mkdir(parents=True)

    def yaz(ad, o):
        (hedef / ad).write_text(json.dumps(o, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dizin = []
    for i, h in enumerate(havuzlar()):
        n = len(h["toplar"]) if h["cizim"] == "bga" else len(sira({}, h["cizim"]))
        assert all(len(d["pin"]) == n for d in h["desenler"]), h["kilif"]
        assert len({tuple(d["pin"]) for d in h["desenler"]}) == h["dizilim"] >= 3  # dizilimler gerçekten farklı
        yaz(f"{i}.json", h)
        dizin.append({k: h[k] for k in ("kilif", "ayrinti", "cizim", "sembol", "dizilim")} | {"id": i})
    yaz("dizin.json", {"secilmis": cikti, "havuzlar": dizin})
    boyut = sum(f.stat().st_size for f in hedef.iterdir())
    print(len(cikti), "seçilmiş örnek,", len(dizin), "havuz,", sum(h["sembol"] for h in dizin), "sembol,",
          round(boyut / 1024), "kB")


if __name__ == "__main__":
    main()
