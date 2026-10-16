"""Pin karşılaştırma altın testleri: bilinen doğru çiftler ve bilinen tuzaklar.

Veriler ağsız: KiCad pin tablosu (kaynak/) ve EasyEDA yanıt örnekleri (tests/ornek/easyeda/).
"""
import gzip
import json
from pathlib import Path

import pytest

from muadil.easyeda import ayristir
from muadil.pinler import karsilastir, rol

KOK = Path(__file__).resolve().parent.parent
KICAD = json.load(gzip.open(KOK / "kaynak" / "kicad_pinler.json.gz", "rt", encoding="utf-8"))


def kicad(ad):
    return KICAD[ad]["pinler"]


def easyeda(kod):
    return ayristir(json.loads((KOK / "tests" / "ornek" / "easyeda" / f"{kod}.json").read_text(encoding="utf-8")))["pinler"]


@pytest.mark.parametrize("eski,yeni,aile,beklenen", [
    # Klasik tuzak: ikisi de TO-220, pin sırası farklı.
    (lambda: kicad("L7805"), lambda: kicad("L7905"), "regulator", "uyumsuz"),
    (lambda: easyeda("C725349"), lambda: easyeda("C111884"), "regulator", "uyumsuz"),
    # SMD tuzağı: SOT-23 LDO'larda dört ayrı dizilim var.
    (lambda: kicad("XC6206PxxxMR"), lambda: kicad("AP7381-33SA-7"), "regulator", "uyumsuz"),
    (lambda: kicad("XC6206PxxxMR"), lambda: kicad("LM3480-3.3"), "regulator", "uyumsuz"),
    (lambda: kicad("XC6206PxxxMR"), lambda: kicad("AP2127N-3.3"), "regulator", "uyumlu"),
    # AMS1117: orijinal ile UMW klonu ("ADJ(GND)", "VOUT(TAB)" adlarıyla).
    (lambda: easyeda("C6186"), lambda: easyeda("C347222"), "regulator", "uyumlu"),
    # İki kaynak aynı parçada uyuşuyor mu (KiCad 3 pin, EasyEDA tab dahil 4 pin).
    (lambda: kicad("AMS1117-3.3"), lambda: easyeda("C6186"), "regulator", "uyumlu"),
    (lambda: kicad("XC6206PxxxMR"), lambda: easyeda("C6430947"), "regulator", "uyumlu"),
    (lambda: kicad("AP2112K-3.3"), lambda: easyeda("C23380830"), "regulator", "uyumlu"),
    (lambda: kicad("L7905"), lambda: easyeda("C111884"), "regulator", "uyumlu"),
    # MOSFET: AO3400 ile SI2302 (SOT-23, G-S-D).
    (lambda: easyeda("C7603192"), lambda: easyeda("C20628873"), "transistor", "uyumlu"),
    (lambda: kicad("AO3400A"), lambda: easyeda("C7603192"), "transistor", "uyumlu"),
    # Çift op-amp: TI TL072 ile XBLW LM358 ("1IN-" / "IN A-" / KiCad "-" + birim).
    (lambda: easyeda("C67473"), lambda: easyeda("C18723608"), "opamp", "uyumlu"),
    (lambda: kicad("TL072"), lambda: easyeda("C67473"), "opamp", "uyumlu"),
    (lambda: kicad("LM358"), lambda: easyeda("C18212285"), "opamp", "uyumlu"),
    (lambda: easyeda("C67470"), lambda: easyeda("C7934"), "opamp", "uyumlu"),
    # 555: KiCad "~{RST}" ile EasyEDA "RST".
    (lambda: kicad("NE555D"), lambda: easyeda("C7593"), "zamanlayici", "uyumlu"),
    # Dörtlü NAND: KiCad adsız pin + birim, EasyEDA "1A/1B/1Y".
    (lambda: kicad("74HC00"), lambda: easyeda("C10090"), "lojik", "uyumlu"),
    # BJT ile MOSFET aynı SOT-23'te: işlevler farklı.
    (lambda: easyeda("C84104"), lambda: easyeda("C7603192"), "transistor", "uyumsuz"),
])
def test_altin(eski, yeni, aile, beklenen):
    sonuc = karsilastir(eski(), yeni(), aile)
    assert sonuc["sonuc"] == beklenen, sonuc


def test_standart_disi_soic_op249():
    # OP249'un SOIC kılıfı standart dışı (1 +INA, 7 OUTA, 8 -INA); KiCad ve EasyEDA ikisi de böyle diyor.
    op249 = {"8": ["-INA", 0], "1": ["+INA", 0], "6": ["V+", 0], "7": ["OUTA", 0], "2": ["V-", 0],
             "4": ["-INB", 2], "3": ["+INB", 2], "5": ["OUTB", 2]}
    assert karsilastir(kicad("OP249GS"), op249, "opamp")["sonuc"] == "uyumlu"
    assert karsilastir(easyeda("C67473"), op249, "opamp")["sonuc"] == "uyumsuz"


def test_onsemi_egik_cizgili_adlar():
    lm2904 = {"1": ["OUT/A", 0], "2": ["-IN/A", 0], "3": ["+IN/A", 0], "4": ["VEE/GND", 0], "5": ["+IN/B", 0],
              "6": ["-IN/B", 0], "7": ["OUT/B", 0], "8": ["VCC", 0]}
    mc33072 = {"1": ["VOUT1", 0], "2": ["VIN1-", 0], "3": ["VIN1+", 0], "4": ["VEE", 0], "5": ["VIN2+", 0],
               "6": ["VIN2-", 0], "7": ["VOUT2", 0], "8": ["VCC", 0]}
    assert karsilastir(kicad("LM2904"), lm2904, "opamp")["sonuc"] == "uyumlu"
    assert karsilastir(easyeda("C67473"), mc33072, "opamp")["sonuc"] == "uyumlu"


def test_adsiz_pinler_eslesmis_sayilmaz():
    # KiCad'de BAT54A (ortak anot) ve BAT54C (ortak katot) pinleri adsız: "aynı ad" diye uyumlu denmemeli.
    assert karsilastir(kicad("BAT54A"), kicad("BAT54C"), "diyot")["sonuc"] == "belirsiz"
    assert karsilastir(kicad("BAV99"), kicad("BAV70"), "diyot")["sonuc"] == "uyumsuz"


def test_flipflop_q_ve_qbar_ayri():
    a = {"5": ["1Q", 0], "6": ["~{1Q}", 0]}
    b = {"5": ["~{1Q}", 0], "6": ["1Q", 0]}
    assert karsilastir(a, b, "lojik")["sonuc"] == "uyumsuz"
    assert karsilastir(a, a, "lojik")["sonuc"] == "uyumlu"


def test_nc_byp_notlu():
    ap2112 = kicad("AP2112K-3.3")  # 4. pin NC
    byp = {**ap2112, "4": ["BYP", "passive", 1]}
    assert karsilastir(ap2112, byp, "regulator")["sonuc"] == "notlu"


def test_en_shdn_kutup():
    a = {"1": ["VIN", 0], "2": ["GND", 0], "3": ["EN", 0], "4": ["NC", 0], "5": ["VOUT", 0]}
    # Üst çizgisiz SHDN: kutbu belli değil -> belirsiz (doğrudan takılır denmez, uyumsuz da denmez).
    assert karsilastir(a, {**a, "3": ["SHDN", 0]}, "regulator")["sonuc"] == "belirsiz"
    # Üst çizgili SHDN = yüksekte açık = EN ile aynı.
    assert karsilastir(a, {**a, "3": ["~{SHDN}", 0]}, "regulator")["sonuc"] == "uyumlu"
    assert karsilastir(a, {**a, "3": ["Shutdown#", 0]}, "regulator")["sonuc"] == "uyumlu"
    # Etkin-düşük EN: gerçekten ters.
    assert karsilastir(a, {**a, "3": ["EN#", 0]}, "regulator")["sonuc"] == "uyumsuz"


def test_numara_adli_pin_belirsiz():
    a = {"1": ["VIN", 0], "2": ["GND", 0], "3": ["VOUT", 0]}
    numara = {"1": ["1", 0], "2": ["2", 0], "3": ["3", 0]}
    assert karsilastir(a, numara, "regulator")["sonuc"] == "belirsiz"
    # İki taraf da yalnız numaralıysa "aynı ad" diye uyumlu sayılmaz.
    assert karsilastir(numara, numara, "regulator")["sonuc"] == "belirsiz"
    assert karsilastir({**a, "4": ["NC", 0]}, {**a, "4": ["4", 0]}, "regulator")["sonuc"] == "belirsiz"


def test_kanal_karisik():
    a = {"1": ["OUTA", 0], "2": ["INA-", 0], "3": ["INA+", 0], "4": ["V-", 0],
         "5": ["INB+", 0], "6": ["INB-", 0], "7": ["OUTB", 0], "8": ["V+", 0]}
    b = {**a, "2": ["INB-", 0], "6": ["INA-", 0]}
    assert karsilastir(a, b, "opamp")["sonuc"] == "uyumsuz"


def test_kanal_ters_numara_uyumlu():
    # Kanal adları ters ama pin grupları aynı: A<->B eşlemesi bire bir, pin uyumu bozulmaz.
    a = {"1": ["OUTA", 0], "2": ["INA-", 0], "3": ["INA+", 0], "4": ["V-", 0],
         "5": ["INB+", 0], "6": ["INB-", 0], "7": ["OUTB", 0], "8": ["V+", 0]}
    b = {"1": ["OUTB", 0], "2": ["INB-", 0], "3": ["INB+", 0], "4": ["V-", 0],
         "5": ["INA+", 0], "6": ["INA-", 0], "7": ["OUTA", 0], "8": ["V+", 0]}
    assert karsilastir(a, b, "opamp")["sonuc"] == "uyumlu"


@pytest.mark.parametrize("ad,aile,beklenen", [
    ("VIN", "regulator", ("IN", None)), ("VI", "regulator", ("IN", None)),
    ("ADJ(GND)", "regulator", ("ADJ|GND", None)), ("VOUT(TAB)", "regulator", ("OUT|TAB", None)),
    ("IN A+", "opamp", ("IN+", 1)), ("1IN-", "opamp", ("IN-", 1)), ("-IN2", "opamp", ("IN-", 2)),
    ("OUTB", "opamp", ("OUT", 2)), ("VCC-", "opamp", ("V-", None)), ("~{RST}", "zamanlayici", ("RST", None)),
    ("3Y", "lojik", ("OUT", 3)), ("N.C.", "regulator", ("NC", None)),
    ("VIN1-", "opamp", ("IN-", 1)), ("VOUT2", "opamp", ("OUT", 2)), ("OUT/A", "opamp", ("OUT", 1)),
    ("-IN/B", "opamp", ("IN-", 2)), ("VEE/GND", "opamp", ("V-", None)),
    ("NEG/2", "opamp", ("IN-", 2)), ("POS3", "opamp", ("IN+", 3)), ("INBP", "opamp", ("IN+", 2)),
    ("INPUTSA-", "opamp", ("IN-", 1)), ("IN+（2）", "opamp", ("IN+", 2)), ("﹣In_A", "opamp", ("IN-", 1)),
    ("VDD+", "opamp", ("V+", None)), ("Ground", "regulator", ("GND", None)), ("ADJUST", "regulator", ("ADJ", None)),
    ("N.C", "regulator", ("NC", None)), ("5", "opamp", ("?", None)),
])
def test_rol(ad, aile, beklenen):
    assert rol(ad, aile) == beklenen


def test_onbellek_birlestir(tmp_path):
    from muadil.easyeda import birlestir, onbellek_oku
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text('{"lcsc":"C1","durum":"yok"}\n{"lcsc":"C2","durum":"yok"}\n', encoding="utf-8")
    b.write_text('{"lcsc":"C2","durum":"var","pinler":{}}\n{"lcsc":"C3","durum":"yok"}\n{yarım', encoding="utf-8")
    assert birlestir(b, a) == 3
    k = onbellek_oku(a)
    assert set(k) == {"C1", "C2", "C3"} and k["C2"]["durum"] == "yok"  # var olan kayıt korunur
