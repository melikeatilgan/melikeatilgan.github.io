"""Bağımsız incelemede bulunan karşı örnekler: hiçbiri yanlışlıkla "doğrudan takılır" ya da "uyumlu" vermemeli."""
from pathlib import Path

from muadil.eslestir import KURALLAR, PinKaynagi, degerlendir, kural_uygula, uretici_tutar
from muadil.pinler import karsilastir


def _kural(aile, ozellik):
    return next(k for k in KURALLAR[aile] if k.ozellik == ozellik)


class GucluPin:
    """Her iki parçaya aynı güçlü pin tablosunu veren sahte kaynak (yalnız kuralları sınamak için)."""

    def __init__(self, pinler):
        self.pinler = pinler

    def bul(self, *a, **k):
        return {"pinler": self.pinler, "guven": "iki kaynak", "kaynak": "test"}


def _p(lcsc, aile, kk, ozl, ham=None, alt=""):
    return {"lcsc": lcsc, "mpn": lcsc, "aile": aile, "alt": alt, "kilif_k": kk, "ozl": ozl, "ham": ham or {}, "uretici": None}


SICAKLIK = {"Operating Temperature": {"temperature min": [-55.0, "temperature"], "temperature max": [150.0, "temperature"]}}


def test_bos_ozellikli_direnc_dogrudan_olmaz():
    assert degerlendir(_p("C1", "direnc", "0603", {}), _p("C2", "direnc", "0603", {}), None)["sinif"] == "kontrol"


def test_okunamayan_eski_deger_atlanmaz():
    ortak = {"Resistance": {"resistance": [1000.0, "resistance"]},
             "Tolerance": {"tolerance min": [-1.0, "percentage"], "tolerance max": [1.0, "percentage"]}}
    eski = {**ortak, "Power": {"power": ["UNKNOWN", "power"]}}
    yeni = {**ortak, "Power": {"power": [0.01, "power"]}}
    assert degerlendir(_p("C1", "direnc", "0603", eski), _p("C2", "direnc", "0603", yeni), None)["sinif"] == "kontrol"


def test_farkli_vgs_rdson_dogrudan_olmaz():
    gsd = {"1": ["G", 0], "2": ["S", 0], "3": ["D", 0]}
    taban = {"Type": {"t": ["N-Channel", "identifier"]}, "Drain to Source Voltage": {"Vds": [30.0, "voltage"]},
             "Number": {"n": [1, "count"]}, "Continuous Drain Current (Id)": {"Id": [3.0, "current"]},
             "Gate Threshold Voltage (Vgs(th) @ Id)": {"Vgs": [1.5, "voltage"]}, **SICAKLIK}
    a = {**taban, "Drain-Source On Resistance (RDS(on))": {"Rds": [0.048, "resistance"], "Vgs": [2.5, "voltage"]}}
    b = {**taban, "Drain-Source On Resistance (RDS(on))": {"Rds": [0.0265, "resistance"], "Vgs": [10.0, "voltage"]}}
    s = degerlendir(_p("C1", "transistor", "SOT-23-3", a, alt="MOSFETs"), _p("C2", "transistor", "SOT-23-3", b, alt="MOSFETs"),
                    GucluPin(gsd))
    assert s["sinif"] == "farkli" and "Vgs" not in str(s["ihlal"])


def test_besleme_araliginin_alti_korunur():
    k = _kural("lojik", "Voltage - Supply")
    assert k.ham
    assert kural_uygula(k, {}, {}, {"Voltage - Supply": "2.7V~5.5V"}, {"Voltage - Supply": "4.5V~6V"})[0] == "ihlal"
    assert kural_uygula(k, {}, {}, {"Voltage - Supply": "2.7V~5.5V"}, {"Voltage - Supply": "1.65V~5.5V"})[0] == "tamam"


def test_farkli_akimda_vf_karsilastirilmaz():
    k = _kural("diyot", "Forward Voltage (Vf @ If)")
    a = {k.ozellik: {"Vf": [0.7, "voltage"], "current": [1.0, "current"]}}
    b = {k.ozellik: {"Vf": [0.6, "voltage"], "current": [0.001, "current"]}}
    assert kural_uygula(k, a, b)[0] == "bilinmiyor"


def test_negatif_ioh_buyuklukle_karsilastirilir():
    k = _kural("lojik", "Current - Output High(Ioh)")
    a = {k.ozellik: {"current": [-0.008, "current"]}}
    b = {k.ozellik: {"current": [-0.002, "current"]}}
    assert kural_uygula(k, a, b)[0] == "zayif"


def test_dielektrik_sicaklik_ve_degisim():
    k = _kural("mlcc", "Temperature Coefficient")
    d = lambda kod: {k.ozellik: {"coefficient": [kod, "temperature_coefficient_code"]}}  # noqa: E731
    assert kural_uygula(k, d("X7S"), d("X5R"))[0] == "ihlal"   # 125 °C yerine 85 °C
    assert kural_uygula(k, d("X7R"), d("X7S"))[0] == "ihlal"   # ±%15 yerine ±%22
    assert kural_uygula(k, d("X7R"), d("C0G"))[0] == "tamam"
    assert kural_uygula(k, d("X5R"), d("X7R"))[0] == "tamam"
    assert kural_uygula(k, d("C0G"), d("X7R"))[0] == "ihlal"


def test_mux_girisleri_yer_degistiremez():
    a = {"1": ["A1", 0], "2": ["B1", 0], "3": ["Y1", 0]}
    b = {"1": ["B1", 0], "2": ["A1", 0], "3": ["Y1", 0]}
    assert karsilastir(a, b, "lojik")["sonuc"] == "uyumsuz"


def test_eksik_sinyal_pini_baska_kanaldan_onaylanmaz():
    tam = {"1": ["OUTA", 0], "2": ["INA-", 0], "3": ["INA+", 0], "4": ["V-", 0],
           "5": ["INB+", 0], "6": ["INB-", 0], "7": ["OUTB", 0], "8": ["V+", 0]}
    eksik = {k: v for k, v in tam.items() if k != "7"}
    assert karsilastir(tam, eksik, "opamp")["sonuc"] == "belirsiz"


def test_nc_ile_dnc_ayni_degil():
    assert karsilastir({"1": ["NC", 0]}, {"1": ["DNC", 0]}, "regulator")["sonuc"] == "belirsiz"


def test_ek_islevli_pinler():
    assert karsilastir({"3": ["EN", 0]}, {"3": ["EN/UVLO", 0]}, "regulator")["sonuc"] == "belirsiz"
    assert karsilastir({"4": ["BYP", 0]}, {"4": ["NR/SS", 0]}, "regulator")["sonuc"] == "belirsiz"


def test_beklenen_buyukluk_yoksa_baskasina_gecilmez():
    k = _kural("regulator", "Output Current")
    assert kural_uygula(k, {k.ozellik: {"current": [1.0, "current"]}}, {k.ozellik: {"voltage": [5.0, "voltage"]}})[0] == "bilinmiyor"


def test_resmi_olmayan_alan_adi_ureticiyi_dogrulamaz():
    assert not uretici_tutar("https://toshiba-distributor.example/a.pdf", "Toshiba")
    assert uretici_tutar("https://toshiba.semicon-storage.com/info/x.pdf", "Toshiba")


def test_islevsel_ek_onek_eslesmesinde_atilmaz():
    pk = PinKaynagi(easyeda_yolu=Path("yok.jsonl"))
    assert pk.kicad_bul("LTC6102IMS8-1", "MSOP-8") == "LTC6102xMS8-1"
    # Varyant kütüphanede olmasaydı "-1" atılıp yanlış sembol seçilmemeli.
    pk.taban.pop("LTC6102XMS8-1", None)
    pk.desen = {k: [(d, ad) for d, ad in v if ad != "LTC6102xMS8-1"] for k, v in pk.desen.items()}
    assert pk.kicad_bul("LTC6102IMS8-1", "MSOP-8") is None


def test_ayni_buyuklugun_baska_adi_okunur():
    k = _kural("opamp", "Input Voltage Noise Density")
    a = {"Noise Density(E N)": {"density": [18e-9, "voltage_noise_density"]}}
    b = {"Input Voltage Noise Density": {"density": [25e-9, "voltage_noise_density"]}}
    assert kural_uygula(k, a, b)[0] == "zayif"


# İkinci bağımsız test (15.10.2026): canlı sitede yanlışlıkla "doğrudan" çıkan çiftler. Değerler katalogdan.
HC14 = {"Series": {"identifier": ["74HC", "identifier"]}, "Number of Circuits": {"count": [6, "count"]},
        "Input Type": {"identifier": ["Schmitt trigger", "identifier"]}, **SICAKLIK}
HAM_HC = {"Voltage - Supply": "2V~6V"}
INV_PIN = {"1": ["1A", 0], "2": ["1Y", 0], "7": ["GND", 0], "14": ["VCC", 0]}


def _hc(ozl):
    return _p("C1", "lojik", "SOIC-14", ozl, HAM_HC, alt="Inverters")


def test_iki_tarafta_eksik_zorunlu_deger_atlanmaz():
    # SN74HC04DR'de giriş tipi yok, ikisinde de çıkış yapısı yok: eskiden "doğrudan" çıkıyordu.
    hc04 = {k: v for k, v in HC14.items() if k != "Input Type"}
    s = degerlendir(_hc(HC14), _hc(hc04), GucluPin(INV_PIN))
    assert s["sinif"] == "kontrol" and any("iki parçada da" in x for x in s["eksik"])


def test_schmitt_girisin_yerine_standart_giris_olmaz():
    tam = {**HC14, "Output Type": {"output type 1": ["Push-Pull", "identifier"]}}
    hc04 = {**tam, "Input Type": {"identifier": ["StandardCMOS", "identifier"]}}
    assert degerlendir(_hc(tam), _hc(hc04), GucluPin(INV_PIN))["sinif"] == "uygun_degil"
    assert degerlendir(_hc(tam), _hc(dict(tam)), GucluPin(INV_PIN))["sinif"] == "dogrudan"
    k = _kural("lojik", "Input Type")  # Çince yazılış aynı şey
    assert kural_uygula(k, HC14, {k.ozellik: {"identifier": ["施密特触发器", "identifier"]}})[0] == "tamam"


def test_lojik_cikis_yapisi_ve_devre_sayisi():
    k = _kural("lojik", "Output Type")  # 74HC05 (open-drain) 74HC04'ün yerine geçmez
    od, pp = ({k.ozellik: {"o": [v, "identifier"]}} for v in ("Open-drain", "Push-pull"))
    assert kural_uygula(k, pp, od)[0] == "ihlal"
    assert kural_uygula(k, od, {k.ozellik: {"o": ["Push-Pull、Open Drain", "identifier"]}})[0] == "tamam"
    n = _kural("lojik", "Number of Gates")  # JLC'de Inverters için alanın adı "Number of Circuits"
    assert kural_uygula(n, HC14, {"Number of Circuits": {"count": [1, "count"]}})[0] == "ihlal"


def test_opamp_besleme_alt_ve_ust_siniri():
    k = _kural("opamp", "Single Supply")
    cift = lambda v: {"Dual Supply": {"default": [v, "string"]}}  # noqa: E731
    tl072, ad8620 = cift("-15V~-5V、5V~15V"), cift("-13V~-5V、5V~13V")
    assert kural_uygula(k, tl072, ad8620)[0] == "ihlal"     # ±13 V'ta biter, ±15 V'luk devreye olmaz
    assert kural_uygula(k, tl072, tl072)[0] == "tamam"
    assert kural_uygula(k, ad8620, cift("-18V~-2.25V、2.25V~18V"))[0] == "tamam"
    tek = lambda a, b: {"Single Supply": {"voltage min": [a, "voltage"], "voltage max": [b, "voltage"]}}  # noqa: E731
    assert kural_uygula(k, tek(3.0, 32.0), tek(2.7, 36.0))[0] == "tamam"   # LM358 -> OPA2171
    assert kural_uygula(k, tek(2.7, 36.0), tek(3.0, 32.0))[0] == "ihlal"
    pm = {"Dual Supply": {"voltage min": [-16.0, "voltage"], "voltage max": [16.0, "voltage"]}}  # "±16V": alt sınır yok
    assert kural_uygula(k, tek(3.0, 32.0), pm)[0] == "bilinmiyor"
    assert kural_uygula(k, cift("-1.5V~16V"), tl072)[0] == "bilinmiyor"  # tek anlamlı okunamayan biçim tahmin edilmez


def test_opamp_cikis_tipi_rail_to_rail():
    k = _kural("opamp", "Output Type")
    rrio = {"Rail to Rail": {"rail to rail 1": ["Rail-to-Rail Input", "identifier"], "rail to rail 2": ["Rail-to-Rail Output", "identifier"]}}
    rro = {"Rail to Rail": {"rail to rail 1": ["Rail-to-rail output", "identifier"]}}
    assert kural_uygula(k, rrio, rro)[0] == "ihlal"   # giriş rail-to-rail değil artık
    assert kural_uygula(k, rro, rrio)[0] == "tamam"
    # LM358'de alan yok: OPA2171'in çıkışı rail-to-rail diye "doğrudan" denmez.
    lm358 = {"Number of Channels": {"count": [2, "count"]}, **SICAKLIK,
             "Single Supply": {"voltage min": [3.0, "voltage"], "voltage max": [32.0, "voltage"]}}
    opa = {**lm358, **rro, "Single Supply": {"voltage min": [2.7, "voltage"], "voltage max": [36.0, "voltage"]}}
    pin = {"1": ["OUTA", 0], "4": ["V-", 0], "8": ["V+", 0]}
    a, b = (_p(c, "opamp", "SOIC-8", o, alt="Operational Amplifier") for c, o in (("C5423", lm358), ("C40904", opa)))
    assert degerlendir(a, b, GucluPin(pin))["sinif"] == "kontrol"


def test_bjt_ft_en_az_en_cok_ayrimi_kaybolmaz():
    # MMBT3904: fT en az 300 MHz; MMBT5551: en çok 300 MHz (en az 100). Katalog ikisine de "300MHz" yazıyor.
    k = _kural("transistor", "Transition Frequency (F T)")
    f = {k.ozellik: {"frequency": [300e6, "frequency"]}}
    assert kural_uygula(k, f, f)[0] == "bilinmiyor"
    ortak = {"Type": {"t": ["NPN", "identifier"]}, "Number": {"n": [1, "count"]}, **SICAKLIK, **f,
             "Collector-Emitter Voltage (VCEO)": {"voltage": [40.0, "voltage"]}, "Current - Collector(Ic)": {"current": [0.2, "current"]},
             "DC Current Gain": {"gain": [100.0, "ratio"]}, "Emitter-Base Voltage (VEBO)": {"voltage": [6.0, "voltage"]}}
    mmbt5551 = {**ortak, "Collector-Emitter Voltage (VCEO)": {"voltage": [160.0, "voltage"]}, "DC Current Gain": {"gain": [300.0, "ratio"]}}
    bep = {"1": ["B", 0], "2": ["E", 0], "3": ["C", 0]}
    a, b = (_p(c, "transistor", "SOT-23-3", o, alt="Bipolar (BJT)") for c, o in (("C7420353", ortak), ("C408396", mmbt5551)))
    assert degerlendir(a, b, GucluPin(bep))["sinif"] == "kontrol"


def test_vebo_gerilemesi_fark_olarak_yazilir():
    k = _kural("transistor", "Emitter-Base Voltage (VEBO)")  # BC847B 6 V -> S9014 5 V
    assert kural_uygula(k, {k.ozellik: {"voltage": [6.0, "voltage"]}}, {k.ozellik: {"voltage": [5.0, "voltage"]}})[0] == "zayif"


def test_diyot_yapisi_ham_metinden_okunur():
    # Normalleştirici ikisini de {"diode pairs": 1} yapıyor; ortak katot ile ortak anot aynı değil.
    k = _kural("diyot", "Diode Configuration")
    cc, ca = ({k.ozellik: {"diode pairs": [1.0, "count"]}} for _ in range(2))
    assert kural_uygula(k, cc, ca, {k.ozellik: "1 Pair Common Cathode"}, {k.ozellik: "1 Pair Common Anode"})[0] == "ihlal"


def _node(js):
    """Site kodunu Node'da, sahte DOM ve sahte fetch ile çalıştırır; son console.log satırını JSON olarak döndürür."""
    import json
    import shutil
    import subprocess

    import pytest
    if not shutil.which("node"):
        pytest.skip("node yok")
    site = Path(__file__).resolve().parent.parent / "site" / "muadil"
    on = f"""import fs from "node:fs"; import {{ pathToFileURL }} from "node:url";
const SITE = {json.dumps(str(site))};
const kod = (ad, kes) => fs.readFileSync(SITE + "/" + ad, "utf8").replace(/^import.*$/m, "").split(kes)[0];
const el = new Map();
const e = (s) => el.get(s) ?? el.set(s, {{ innerHTML: "", textContent: "", value: "", scrollIntoView() {{}},
  insertAdjacentHTML(_, x) {{ this.innerHTML += x; }} }}).get(s);
const api = {{ h: (x) => String(x ?? ""), sayi: String, dolar: String, hazirla: async () => ({{}}) }};
"""
    r = subprocess.run(["node", "--input-type=module", "-e", on + js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_eski_arama_yaniti_yeni_sonucu_ezmez():
    # Önce C6186, hemen sonra C2040 aranıyor; ilk istek geç biterse ekranda yine C2040 kalmalı.
    assert _node("""
const bekleyen = new Map();
Object.assign(api, { parca: (c) => new Promise((r) => bekleyen.set(c, r)), bul: async () => ({ birebir: [], yakin: [] }) });
const app = Function("api", "document", "history", `const {h,sayi,dolar,hazirla,parca,bul}=api;${kod("app.js", "sonuc.addEventListener")};return {ara};`)(
  api, { querySelector: e }, { replaceState() {} });
const ilk = app.ara("C6186"), ikinci = app.ara("C2040");
bekleyen.get("C2040")({ c: "C2040", m: "RP2040" }); await ikinci;
bekleyen.get("C6186")({ c: "C6186", m: "AMS1117-3.3" }); await ilk;
console.log(JSON.stringify({ yeni: e("#sonuc").innerHTML.includes("RP2040"), eski: e("#sonuc").innerHTML.includes("AMS1117") }));
""") == {"yeni": True, "eski": False}


SAHTE_VERI = """
const dosya = { "meta.json": { kova: 2000 }, "ara/_dizin.json": ["AM", "LM_", "LMV", ...[..."0123456789"].map((x) => "LM" + x), "__"].sort(),
  "ara/LM_.json": [["LM", "C1", "u", "k", 1]], "ara/LM0.json": [["LM0070", "C2", "u", "k", 1]],
  "ara/LM3.json": [["LM358DR", "C5423", "u", "k", 9]], "ara/LMV.json": [["LMV358", "C3", "u", "k", 1]] };
const bozuk = new Set(DOSYA_BOZUK);
globalThis.fetch = async (url) => {
  const yol = url.slice("veri/".length);
  if (bozuk.has(yol)) return new Response("", { status: 503 });
  return yol in dosya || yol.startsWith("ara/") ? Response.json(dosya[yol] ?? []) : new Response("", { status: 404 });
};
const v = await import(pathToFileURL(SITE + "/veri.js"));
await v.hazirla();
const dene = (f) => f.then((x) => x, (h) => "HATA " + h.message);
"""


def test_iki_harfli_arama_alt_dosyalari_okur():
    # "__" dosyası (boş anahtar) her sorgunun öneki sayılıyordu: "LM" yalnız onu okuyup boş dönüyordu.
    s = _node(SAHTE_VERI.replace("DOSYA_BOZUK", "[]") + """
const lm = await v.bul("LM"), lm358 = await v.bul("LM358");
console.log(JSON.stringify({ birebir: lm.birebir.map((x) => x[0]), yakin: lm.yakin.map((x) => x[0]), eksik: lm.eksik,
  lm358: lm358.yakin.map((x) => x[0]), eksik358: lm358.eksik }));
""")
    # LM0..LM9 + LMV + LM_ = 12 alt dosya, 8'i okunur: tam eşleşme dosyası (LM_) önce, sonra LM0..LM6; sonuç eksik işaretli.
    assert s == {"birebir": ["LM"], "yakin": ["LM0070", "LM358DR"], "eksik": True, "lm358": ["LM358DR"], "eksik358": False}


def test_okunamayan_dosya_katalogda_yok_sayilmaz():
    s = _node(SAHTE_VERI.replace("DOSYA_BOZUK", '["ara/AM.json", "p/3.json"]') + """
console.log(JSON.stringify({ ara: await dene(v.bul("AMS1117-3.3")), parca: await dene(v.parca("C6186")),
  yok: await dene(v.parca("C99999999")) }));
""")
    assert s == {"ara": "HATA ara/AM.json: 503", "parca": "HATA p/3.json: 503", "yok": None}


def test_bom_kurali_olmayan_parca_sorunsuz_sayilmaz():
    s = _node("""
Object.assign(api, { parca: async (c) => { if (c === "C1") throw new Error("p/0.json: 503");
  return { c, m: "STM32F103C8T6", u: "ST", k: "LQFP-48", s: 247628, sn: "tercihli" }; } });
const bom = Function("api", "document", `const {h,sayi,dolar,hazirla,parca,bul}=api;${kod("bom.js", '$("#calistir").addEventListener')};return {calistir};`)(
  api, { querySelector: e });
e("#girdi").value = ["Comment,LCSC,Quantity", "STM32F103C8T6,C8734,1", "X,C1,1"].join(String.fromCharCode(10));
await bom.calistir();
console.log(JSON.stringify({ ozet: e("#ozet").innerHTML, rapor: e("#rapor").innerHTML }));
""")
    assert "Sorunsuz: 0" in s["ozet"] and "Muadil kuralı yok: 1" in s["ozet"]
    assert ">Sorunsuz<" not in s["rapor"]
    assert "Okunamadı: 1" in s["ozet"] and "Katalogda yok" not in s["ozet"]


def test_pf_degerleri_ayni_havuza_dusmez():
    # round(v, 9): 100 pF = 1e-10 F ile 6,8 pF ikisi de 0.0 oluyordu; 100 pF'lık eşi 250 aday sınırında kayboluyordu.
    from muadil.yayinla import grup_anahtari
    c = lambda f: {"aile": "mlcc", "alt": "Multilayer Ceramic Capacitors MLCC - SMD/SMT", "ham": {},  # noqa: E731
                   "ozl": {"Capacitance": {"capacitance": [f, "capacitance"]}}}
    assert grup_anahtari(c(100e-12)) != grup_anahtari(c(6.8e-12))
    assert grup_anahtari(c(4.7e-9)) != grup_anahtari(c(5.1e-9))
    assert grup_anahtari(c(100e-12)) == grup_anahtari(c(1e-10 * (1 + 1e-12)))  # kayan nokta gürültüsü aynı havuz


def test_kanal_basina_ve_paket_akimi_karsilastirilmaz():
    # LM358: 700 µA paket toplamı; OPA2171: 475 µA kanal başına (950 µA paket). Katalogda ikisi de "Quiescent Current".
    k = _kural("opamp", "Quiescent Current")
    a, b = {k.ozellik: {"current": [700e-6, "current"]}}, {k.ozellik: {"current": [475e-6, "current"]}}
    s = kural_uygula(k, a, b)
    assert s[0] == "bilinmiyor" and "kanal başına" in s[1]
