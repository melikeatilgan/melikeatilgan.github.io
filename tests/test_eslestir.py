"""Muadil kuralları, kılıf adları ve KiCad sembol eşlemesi testleri."""
import json
from pathlib import Path

import pytest

from muadil.eslestir import KURALLAR, PinKaynagi, degerlendir, kilif_pin_sayisi, kural_uygula
from muadil.katalog import aile, kilif_k

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pk():
    return PinKaynagi()


@pytest.mark.parametrize("ham,ortak", [
    ("SOT-23", "SOT-23-3"), ("SOT-23-3L", "SOT-23-3"), ("SOT-23(TO-236)", "SOT-23-3"), ("SOP-8", "SOIC-8"),
    ("SOIC-8", "SOIC-8"), ("SOP-8_150mil", "SOIC-8"), ("TO-220AB", "TO-220-3"), ("SOT223", "SOT-223"),
    ("SOT-223-4", "SOT-223"), ("SMA(DO-214AC)", "SMA"), ("TO-263-3", "TO-263"), ("0603", "0603"),
    ("SOT-23-5", "SOT-23-5"), ("TSOT-23-5", "TSOT-23-5"),  # ince kılıf ayrı tutulur
])
def test_kilif_k(ham, ortak):
    assert kilif_k(ham) == ortak


def test_kilif_pin_sayisi():
    assert [kilif_pin_sayisi(k) for k in ["SOT-223", "SOIC-8", "SOT-23-5", "TO-252", "TO-220-3"]] == [None, 8, 5, None, 3]


@pytest.mark.parametrize("mpn,kk,sembol", [
    ("AMS1117-3.3V", "SOT-223", "AMS1117-3.3"), ("LM358DR", "SOIC-8", "LM358"), ("TL072CDR(UMW)", "SOIC-8", "TL072"),
    ("NE555DR", "SOIC-8", "NE555D"), ("XC6206P332MR", "SOT-23-3", "XC6206PxxxMR"), ("LM7805CT", "TO-220-3", "LM7805_TO220"),
    ("SN74HC00DR", "SOIC-14", "74HC00"), ("LM317T", "TO-220-3", "LM317_TO-220"), ("LM317", "SOT-223", "LM317_SOT-223"),
    # Kılıf ya da pin sayısı tutmuyorsa eşleşme yok:
    ("XC6206P332MR", "SOT-23-5", None), ("LM358", "DFN-8(2X2)", None), ("LM3171", "TO-220-3", None),
])
def test_kicad_bul(pk, mpn, kk, sembol):
    assert pk.kicad_bul(mpn, kk) == sembol


def test_uretici_tutar():
    from muadil.eslestir import uretici_tutar
    assert uretici_tutar("https://www.torexsemi.com/file/xc6206/XC6206.pdf", "Torex Semicon")
    assert not uretici_tutar("https://www.torexsemi.com/file/xc6206/XC6206.pdf", "UMW(Youtai Semiconductor Co., Ltd.)")
    assert uretici_tutar("http://www.ti.com/lit/ds/symlink/tl071.pdf", "Texas Instruments")
    assert not uretici_tutar("http://www.st.com/x.pdf", "ST(Semtech)")  # kısa adlar karışmasın
    assert not uretici_tutar("", "Texas Instruments")


def test_tek_harf_ek_zayif(pk):
    # LM317L (100 mA, TO-92) LM317'nin işlevce farklı sürümü; tek harfli ekle bulunan sembol güçlü sayılmaz.
    assert pk.kicad_esle("NE555DR", "SOIC-8") == ("NE555D", "R")
    s = pk.bul("C9000030", "NE555DR", "SOIC-8", "zamanlayici", "Texas Instruments")
    assert s["guven"] == "kicad ad"
    s = pk.bul("C9000031", "LM358DR", "SOIC-8", "opamp", "Texas Instruments")
    assert s["guven"] == "kicad uretici"  # iki harfli ambalaj eki (DR)


def test_aile():
    assert aile("Power Management (PMIC)", "Voltage Regulators - Linear, Low Drop Out (LDO) Regulators") == "regulator"
    assert aile("Amplifiers/Comparators", "Comparators") == "opamp"
    assert aile("Amplifiers/Comparators", "Audio Amplifiers") == "genel"
    assert aile("Transistors/Thyristors", "MOSFETs") == "transistor"
    assert aile("Resistors", "Chip Resistor - Surface Mount") == "direnc"


def _ozl(**alanlar):
    return {k.replace("_", " "): v for k, v in alanlar.items()}


def _kural(aile_adi, ozellik):
    return next(k for k in KURALLAR[aile_adi] if k.ozellik == ozellik)


def test_en_az_ve_zorunlu():
    k = _kural("regulator", "Output Current")
    eski = {"Output Current": {"current": [1.0, "current"]}}
    assert kural_uygula(k, eski, {"Output Current": {"current": [1.5, "current"]}})[0] == "tamam"
    assert kural_uygula(k, eski, {"Output Current": {"current": [0.8, "current"]}})[0] == "ihlal"
    assert kural_uygula(k, eski, {})[0] == "bilinmiyor"
    # Eskide değer yoksa adayın onu karşıladığı söylenemez; iki tarafta da yoksa kural uygulanmaz.
    assert kural_uygula(k, {}, eski)[0] == "bilinmiyor"
    assert kural_uygula(k, {}, {}) is None


def test_sicaklik_kapsar():
    k = _kural("regulator", "Operating Temperature")
    eski = {"Operating Temperature": {"temperature min": [-40.0, "temperature"], "temperature max": [125.0, "temperature"]}}
    dar = {"Operating Temperature": {"temperature min": [0.0, "temperature"], "temperature max": [125.0, "temperature"]}}
    genis = {"Operating Temperature": {"temperature min": [-55.0, "temperature"], "temperature max": [150.0, "temperature"]}}
    assert kural_uygula(k, eski, dar)[0] == "ihlal"
    assert kural_uygula(k, eski, genis)[0] == "tamam"


def test_dielektrik_ve_tolerans():
    d = _kural("mlcc", "Temperature Coefficient")
    x7r = {"Temperature Coefficient": {"coefficient": ["X7R", "temperature_coefficient_code"]}}
    c0g = {"Temperature Coefficient": {"coefficient": ["C0G", "temperature_coefficient_code"]}}
    y5v = {"Temperature Coefficient": {"coefficient": ["Y5V", "temperature_coefficient_code"]}}
    assert kural_uygula(d, x7r, c0g)[0] == "tamam"
    assert kural_uygula(d, x7r, y5v)[0] == "ihlal"
    t = _kural("direnc", "Tolerance")
    yuzde1 = {"Tolerance": {"tolerance min": [-1.0, "percentage"], "tolerance max": [1.0, "percentage"]}}
    yuzde5 = {"Tolerance": {"tolerance min": [-5.0, "percentage"], "tolerance max": [5.0, "percentage"]}}
    assert kural_uygula(t, yuzde1, yuzde5)[0] == "ihlal"
    assert kural_uygula(t, yuzde5, yuzde1)[0] == "tamam"


def test_rdson_farkli_vgs_karsilastirilmaz():
    k = _kural("transistor", "Drain-Source On Resistance (RDS(on))")
    a = {k.ozellik: {"Rds": [0.048, "resistance"], "Vgs": [2.5, "voltage"]}}
    b = {k.ozellik: {"Rds": [0.0265, "resistance"], "Vgs": [10.0, "voltage"]}}
    assert kural_uygula(k, a, b)[0] == "bilinmiyor"


def _parca(lcsc, mpn, kk, ozl, aile_adi="regulator", uretici=None):
    return {"lcsc": lcsc, "mpn": mpn, "kilif_k": kk, "aile": aile_adi, "ozl": ozl, "uretici": uretici}


AMS = "Advanced Monolithic Systems"


LDO = {"Output Configuration": {"polarity 1": ["Positive", "identifier"]}, "Output Type": {"t": ["Fixed", "identifier"]},
       "Output Voltage": {"voltage": [3.3, "voltage"]}, "Output Current": {"current": [1.0, "current"]},
       "Supply Voltage": {"voltage": [15.0, "voltage"]}, "Number of Outputs": {"count": [1, "count"]},
       "Operating Temperature": {"temperature min": [-40.0, "temperature"], "temperature max": [125.0, "temperature"]}}


def test_sinif_pin_verisi_olmadan_dogrudan_olmaz():
    a = _parca("C1", "YOK-1", "SOT-223", LDO)
    b = _parca("C2", "YOK-2", "SOT-223", LDO)
    assert degerlendir(a, b, None)["sinif"] == "kontrol"


def test_sinif_pinli_dogrudan(pk):
    # KiCad'in AMS1117 sembolü AMS'nin datasheet'ine bağlı: aynı üreticinin parçaları için güçlü kanıt.
    a = _parca("C9000001", "AMS1117-3.3", "SOT-223", LDO, uretici=AMS)
    b = _parca("C9000002", "AMS1117-3.3", "SOT-223", LDO, uretici=AMS)
    assert degerlendir(a, b, pk)["sinif"] == "dogrudan"
    # Tek harf ekli ad ("-3.3V") temkinli olarak zayıf sayılır: kontrol gerekli.
    c = _parca("C9000009", "AMS1117-3.3V", "SOT-223", LDO, uretici=AMS)
    assert degerlendir(a, c, pk)["sinif"] == "kontrol"


def test_ada_gore_kicad_dogrudan_olmaz(pk):
    # Başka üreticinin aynı adlı klonu: KiCad tablosu yalnız ada göre, "doğrudan" denmez.
    a = _parca("C9000011", "AMS1117-3.3", "SOT-223", LDO, uretici=AMS)
    b = _parca("C9000012", "AMS1117-3.3", "SOT-223", LDO, uretici="ORNEK KLON")
    s = degerlendir(a, b, pk)
    assert s["sinif"] == "kontrol" and "adına göre" in s["eksik"][-1]


def test_umw_xc6206_ayni_numara_farkli_dizilim():
    # UMW'nin XC6206P332MR'ı (datasheet, Mart 2025): SOT-23'te 1 GND, 2 Input, 3 Output.
    # Torex orijinalinde 2 VOUT, 3 VIN. KiCad sembolü Torex'in; EasyEDA UMW'nin parçasına özel.
    pk = PinKaynagi(easyeda_yolu=Path("yok.jsonl"))
    from muadil.easyeda import ayristir
    umw = ayristir(json.loads((KOK / "tests" / "ornek" / "easyeda" / "C347376.json").read_text(encoding="utf-8")))
    pk.easyeda["C347376"] = {**umw, "lcsc": "C347376"}
    s = pk.bul("C347376", "XC6206P332MR", "SOT-23-3", "regulator", "UMW(Youtai Semiconductor Co., Ltd.)")
    assert s["guven"] == "celiski" and s["kicad"] == "XC6206PxxxMR"
    torex = pk.bul("C9000020", "XC6206P332MR-G", "SOT-23-3", "regulator", "Torex Semicon")
    assert torex["guven"] == "kicad uretici"
    klon = pk.bul("C9000021", "XC6206P332MR", "SOT-23-3", "regulator", "TECH PUBLIC")
    assert klon["guven"] == "kicad ad"


def test_sinif_farkli_kilif_ve_uygun_degil(pk):
    a = _parca("C9000001", "AMS1117-3.3", "SOT-223", LDO, uretici=AMS)
    b = _parca("C9000003", "AMS1117-3.3", "SOT-89-3", LDO, uretici=AMS)
    assert degerlendir(a, b, pk)["sinif"] == "farkli_kilif"
    zayif = {**LDO, "Supply Voltage": {"voltage": [12.0, "voltage"]}}
    c = _parca("C9000004", "AMS1117-3.3", "SOT-223", zayif, uretici=AMS)
    s = degerlendir(a, c, pk)
    assert s["sinif"] == "uygun_degil" and "giriş" in s["ihlal"][0]


def test_7805_7905_uygun_degil(pk):
    poz = {"Output Configuration": {"polarity 1": ["Positive", "identifier"]}}
    a = _parca("C9000005", "L7805CV", "TO-220-3", poz, uretici="STMicroelectronics")
    b = _parca("C9000006", "L7905CV", "TO-220-3", poz, uretici="STMicroelectronics")  # kutup bilerek aynı: pin farkı yakalanmalı
    s = degerlendir(a, b, pk)
    assert s["sinif"] == "uygun_degil" and s["ihlal"][0] == "Pin dizilimi uyumsuz"


def test_kural_adlari_katalogda_var():
    # Normalleştirici bazı adları değiştiriyor ("Vrwm" -> "VRWM"); yanlış adlı kural sessizce hiç uygulanmaz.
    adlar = json.loads((KOK / "tests" / "ornek" / "ozellik_adlari.json").read_text(encoding="utf-8"))
    eksik = [(a, ad) for a, ks in KURALLAR.items() for k in ks if not k.ham for ad in (k.ozellik, *k.diger) if ad not in adlar[a]]
    assert not eksik, eksik


def test_zener_araligi_icinde():
    k = _kural("diyot", "Zener Voltage (Range)")
    c = {k.ozellik: {"voltage min": [4.8, "voltage"], "voltage max": [5.4, "voltage"]}}   # ±%5
    b = {k.ozellik: {"voltage min": [5.0, "voltage"], "voltage max": [5.2, "voltage"]}}   # ±%2
    assert kural_uygula(k, c, b)[0] == "tamam"     # dar toleranslı geniş toleranslının yerine geçer
    assert kural_uygula(k, b, c)[0] == "ihlal"     # tersi olmaz


def test_tvs_vrwm_ve_yon():
    v = _kural("diyot", "Reverse Stand-Off Voltage (VRWM)")
    assert kural_uygula(v, {v.ozellik: {"v": [5.0, "voltage"]}}, {v.ozellik: {"v": [16.0, "voltage"]}})[0] == "ihlal"
    y = _kural("diyot", "Polarity")
    tek = {y.ozellik: {"p": ["Unidirectional", "identifier"]}}
    cift = {y.ozellik: {"p": ["Bidirectional", "identifier"]}}
    assert kural_uygula(y, tek, cift)[0] == "ihlal"
