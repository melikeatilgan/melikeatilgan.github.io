"""Muadil motoru: bir parça için aynı kategorideki adayları kanıtıyla sınıflandırır.

Sınıflar:
  dogrudan  - kılıf aynı, pin dizilimi iki tarafta da biliniyor ve uyumlu, tüm kurallar sağlanıyor
  farkli    - kılıf ve pin uyumlu, zorunlu kurallar sağlanıyor; bazı değerler daha zayıf ya da doğrulanamadı
  kontrol   - kılıf aynı, zorunlu kurallar çiğnenmiyor ama pin verisi ya da bazı değerler eksik
  uygun_degil - pin uyumsuz ya da zorunlu kural çiğneniyor (neden yazılır)
Hiçbir aday kanıtı olmadan "dogrudan" sınıfına giremez. Zorunlu bir değer iki parçada da yoksa
kural atlanmaz: doğrulanamadığı için sınıf en fazla "kontrol" olur.
"""
import gzip
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .easyeda import onbellek_oku
from .katalog import kilif_k
from .pinler import karsilastir

KOK = Path(__file__).resolve().parent.parent
PINSIZ = {"direnc", "mlcc"}  # iki uçlu, kutupsuz: kılıf aynıysa pin uyumu tanımı gereği var
PIN_AILELERI = {"regulator", "opamp", "transistor", "diyot", "zamanlayici", "lojik"}  # KiCad'de aranan aileler
GORECELI = 0.005


@dataclass
class Kural:
    ozellik: str
    anahtar: str | None   # değerin sözlükteki adı; None = ilk değer. Ad varsa ama sözlükte yoksa değer bilinmiyor sayılır
    tur: str              # esit | icerir | en_az | en_cok | kapsar | icinde | tolerans | dielektrik | besleme
    zorunlu: bool
    etiket: str
    kosul: str | None = None  # ölçüm koşulunun anahtarı (RDS(on) için "Vgs"): koşul farklıysa sayılar karşılaştırılmaz
    ham: bool = False         # değer ham metinden okunur (normalleştirici "2V~6V" aralığının altını atıyor)
    diger: tuple = ()         # aynı büyüklüğün katalogdaki başka adları ("Noise Density(E N)")
    yalniz: tuple = ()        # yalnız adında bunlardan biri geçen alt kategorilerde uygulanır (boş: ailenin tümü)
    haric: tuple = ()         # bu alt kategorilerde uygulanmaz (değer kategoriden belli, ör. Inverters'ta işlev)
    belirsiz: str = ""        # katalog sayısının neyi gösterdiği belli değil (neden yazılır): karşılaştırılmaz

    def uygulanir(self, alt: str) -> bool:
        return (not self.yalniz or any(s in alt for s in self.yalniz)) and not any(s in alt for s in self.haric)


R = Kural
MOS, BJT = ("MOSFET",), ("Bipolar", "Digital Transistor")
EN_AZ_MI = "en az mı en çok mu olduğu yazmıyor"
DOGRULTUCU_DISI = ("TVS", "Zener")  # bunlarda Vr / If yerine kendi kuralları var
KURALLAR = {
    "regulator": [
        R("Output Configuration", None, "esit", True, "Çıkış kutbu"),
        R("Output Type", None, "esit", True, "Sabit / ayarlı"),
        R("Output Voltage", "voltage", "esit", True, "Çıkış gerilimi"),
        R("Number of Outputs", "count", "esit", True, "Çıkış sayısı"),
        R("Output Current", "current", "en_az", True, "Çıkış akımı"),
        R("Supply Voltage", "voltage", "en_az", True, "En yüksek giriş gerilimi"),
        R("Operating Temperature", None, "kapsar", True, "Çalışma sıcaklığı"),
        R("Voltage Dropout", "voltage", "en_cok", False, "Düşüm gerilimi", kosul="current"),
        R("Standby Current", "current", "en_cok", False, "Boşta akım", diger=("Quiescent Current", "Supply Current (Iq)")),
        R("Power Supply Rejection Ratio (Psrr)", "level 1", "en_az", False, "PSRR", kosul="frequency 1"),
    ],
    "transistor": [
        R("Type", None, "esit", True, "Tip (N/P, NPN/PNP)"),
        R("Number", None, "esit", True, "Transistör sayısı"),
        R("Drain to Source Voltage", "Vds", "en_az", True, "Vds", yalniz=MOS),
        R("Continuous Drain Current (Id)", "Id", "en_az", True, "Id", yalniz=MOS),
        R("Collector-Emitter Voltage (VCEO)", "voltage", "en_az", True, "Vceo", yalniz=BJT),
        R("Current - Collector(Ic)", "current", "en_az", True, "Ic", yalniz=BJT),
        R("Gate Threshold Voltage (Vgs(th) @ Id)", "Vgs", "en_cok", True, "Eşik gerilimi Vgs(th)", yalniz=MOS),
        R("Operating Temperature", None, "kapsar", True, "Çalışma sıcaklığı"),
        # JLC hFE ve fT için tek sayı veriyor: MMBT3904'te en az 300 MHz, MMBT5551'de en çok 300 MHz, ikisi de "300MHz".
        R("DC Current Gain", "gain", "en_az", True, "Akım kazancı hFE", yalniz=BJT, belirsiz=EN_AZ_MI),
        R("Transition Frequency (F T)", "frequency", "en_az", True, "fT", yalniz=BJT, belirsiz=EN_AZ_MI),
        R("Emitter-Base Voltage (VEBO)", "voltage", "en_az", False, "Vebo", yalniz=BJT),
        R("Drain-Source On Resistance (RDS(on))", "Rds", "en_cok", False, "RDS(on)", kosul="Vgs", yalniz=MOS),
        R("Power Dissipation (Pd)", "power", "en_az", False, "Güç kaybı Pd"),
        R("Total Gate Charge (Qg @ Vgs)", "charge", "en_cok", False, "Kapı yükü Qg", kosul="voltage", yalniz=MOS),
    ],
    "diyot": [
        # Normalleştirici "1 Pair Common Cathode" ile "1 Pair Common Anode"u aynı sayıya (diode pairs: 1) çeviriyor.
        R("Diode Configuration", None, "esit", True, "Diyot yapısı", ham=True, haric=("TVS", "Bridge")),
        R("Reverse Voltage (Vr)", "voltage", "en_az", True, "Ters gerilim Vr", haric=DOGRULTUCU_DISI),
        R("Rectified Current", "current", "en_az", True, "İleri akım", haric=DOGRULTUCU_DISI),
        R("Zener Voltage (Nom)", None, "esit", True, "Zener gerilimi", yalniz=("Zener",)),
        R("Zener Voltage (Range)", None, "icinde", True, "Zener gerilim aralığı", yalniz=("Zener",)),
        R("Polarity", None, "esit", True, "Yön (tek / çift yönlü)", yalniz=("TVS",)),
        R("Number of Channels", None, "esit", True, "Kanal sayısı", yalniz=("TVS",)),
        R("Reverse Stand-Off Voltage (VRWM)", None, "esit", True, "Vrwm", yalniz=("TVS",)),
        R("Peak Pulse Power Dissipation (Ppp)", None, "en_az", True, "Darbe gücü Ppp", yalniz=("TVS",)),
        R("Power Dissipation (Pd)", "power", "en_az", True, "Güç kaybı Pd", yalniz=("Zener", "Switching")),
        R("Forward Voltage (Vf @ If)", "Vf", "en_cok", False, "İleri gerilim Vf", kosul="current"),
        R("Reverse Recovery Time (Trr)", "time", "en_cok", False, "Toparlanma süresi trr"),
        R("Reverse Leakage Current (Ir)", "current", "en_cok", False, "Kaçak akım"),
        R("Clamping Voltage (Max)", None, "en_cok", False, "Kenetleme gerilimi"),
        R("Operating Junction Temperature Range", None, "kapsar", False, "Eklem sıcaklığı aralığı"),
    ],
    "opamp": [
        R("Number of Channels", "count", "esit", True, "Kanal sayısı"),
        # Op-amp kategorisinde JLC çıkış yapısını "Rail to Rail" alanında veriyor (karşılaştırıcıda Output Type).
        R("Output Type", None, "icerir", True, "Çıkış tipi / rail-to-rail", diger=("Rail to Rail",)),
        R("Single Supply", None, "besleme", True, "Besleme aralığı (V+ - V-)",
          diger=("Dual Supply", "Maximum Power Supply Range (Vdd-Vss)")),
        R("Operating Temperature", None, "kapsar", True, "Çalışma sıcaklığı"),
        R("Gain Bandwidth Product", "frequency", "en_az", False, "Kazanç-bant genişliği"),
        R("Slew Rate", None, "en_az", False, "Yükselme hızı"),
        R("VOS - Input Offset Voltage", None, "en_cok", False, "Giriş ofseti"),
        R("Input Voltage Noise Density", "density", "en_cok", False, "Giriş gürültüsü", diger=("Noise Density(E N)",)),
        R("Common Mode Rejection Ratio(CMRR)", "level 1", "en_az", False, "CMRR"),
        R("Ib - Input Bias Current", "current", "en_cok", False, "Giriş kutuplama akımı"),
        R("Response Time (Tr)", "time", "en_cok", False, "Tepki süresi"),
        # LM358 için 700 µA paket toplamı, OPA2171 için 475 µA kanal başına: 475 < 700 ama paket 950 µA çekiyor.
        R("Quiescent Current", "current", "en_cok", False, "Boşta akım", diger=("Quiescent Current(Iq)",),
          belirsiz="kanal başına mı paket toplamı mı olduğu yazmıyor"),
    ],
    "zamanlayici": [
        R("Timer Number", "count", "esit", True, "Zamanlayıcı sayısı"),
        R("Voltage - Supply", None, "kapsar", True, "Besleme aralığı", ham=True),
        R("Operating Temperature", None, "kapsar", True, "Çalışma sıcaklığı"),
        R("Output Current", "current", "en_az", False, "Çıkış akımı"),
        R("Supply Current", "current", "en_cok", False, "Besleme akımı"),
    ],
    "lojik": [
        # İşlevin alt kategoriye göre adı değişiyor; Inverters'ta işlev kategorinin kendisi.
        R("Logic Type", None, "esit", True, "Mantık işlevi", haric=("Inverters",),
          diger=("Type", "Function", "Translator Type", "Output Function", "Channel Type")),
        R("Number of Gates", None, "esit", True, "Kapı / devre sayısı",
          diger=("Number of Circuits", "Number of Elements", "Number of Channels")),
        R("Inputs Per Gates", None, "esit", True, "Kapı başına giriş", yalniz=("Logic Gates",)),
        # 74HC14 (Schmitt) ile 74HC04 (standart CMOS) aynı dizilimde: yalnız bu alan ayırıyor.
        R("Input Type", None, "esit", True, "Giriş tipi (Schmitt / standart / TTL)",
          yalniz=("Logic Gates", "Inverters", "Buffers", "Shift Registers", "Monostable")),
        R("Output Type", None, "icerir", True, "Çıkış yapısı (push-pull / open-drain / 3-state)"),  # 74HC05 / 74HC04
        R("Series", None, "esit", True, "Seri (HC / HCT / LVC ...)", diger=("Logic Family",)),
        R("Voltage - Supply", None, "kapsar", True, "Besleme aralığı", ham=True),
        R("Operating Temperature", None, "kapsar", True, "Çalışma sıcaklığı"),
        R("Propagation Delay", "time", "en_cok", False, "Gecikme"),
        R("Current - Output High(Ioh)", "current", "en_az", False, "Çıkış akımı (Ioh)"),
        R("Current - Output Low(Iol)", "current", "en_az", False, "Çıkış akımı (Iol)"),
    ],
    "direnc": [
        R("Resistance", "resistance", "esit", True, "Direnç"),
        R("Tolerance", None, "tolerans", True, "Tolerans"),
        R("Power", "power", "en_az", True, "Güç"),
        R("Operating Temperature", None, "kapsar", False, "Çalışma sıcaklığı"),
        R("Temperature Coefficient", None, "tolerans", False, "Sıcaklık katsayısı"),
        R("Supply Voltage (Max)", "voltage", "en_az", False, "En yüksek gerilim"),
    ],
    "mlcc": [
        R("Capacitance", "capacitance", "esit", True, "Kapasite"),
        R("Rated Voltage", "voltage", "en_az", True, "Gerilim değeri"),
        R("Temperature Coefficient", None, "dielektrik", True, "Dielektrik"),
        R("Tolerance", None, "tolerans", True, "Tolerans"),
    ],
}

# İki tarafta da bilinmesi gereken temel değerler: biri eksikse "doğrudan" ya da "farklı" denmez.
TEMEL = {
    "regulator": ["Output Voltage", "Output Current", "Output Type"],
    "transistor": ["Type"],
    "opamp": ["Number of Channels"],
    "direnc": ["Resistance", "Tolerance", "Power"],
    "mlcc": ["Capacitance", "Rated Voltage", "Temperature Coefficient", "Tolerance"],
}

# Dielektrik kodu: sınıf 1 (C0G/NP0) -55~125 °C'de neredeyse sabit. Sınıf 2 kodu üç harf:
# alt sıcaklık (X/Y/Z), üst sıcaklık (5/6/7/8), en büyük kapasite değişimi (R/S/T/U/V).
SINIF1 = {"C0G": "C0G", "NP0": "C0G", "COG": "C0G", "NPO": "C0G"}
D_ALT = {"X": -55, "Y": -30, "Z": 10}
D_UST = {"4": 65, "5": 85, "6": 105, "7": 125, "8": 150, "9": 200}
D_DEGISIM = {"P": 10, "R": 15, "L": 15, "S": 22, "T": 33, "U": 56, "V": 82}


def dielektrik(kod: str):
    """(alt °C, üst °C, en büyük % değişim) ya da tanınmazsa None."""
    if SINIF1.get(kod) == "C0G":
        return (-55, 125, 0)
    if len(kod) == 3 and kod[0] in D_ALT and kod[1] in D_UST and kod[2] in D_DEGISIM:
        return (D_ALT[kod[0]], D_UST[kod[1]], D_DEGISIM[kod[2]])
    return None


SAYI = (int, float)
HAM_GERILIM = re.compile(r"(-?\d+(?:\.\d+)?)\s*(m?)V\b")
# Katalogda aynı şeyin başka yazılışları (Çince karşılıklar, "Complementary type" ...); anahtarlar _metin biçiminde.
ESANLAM = {"施密特触发器": "SCHMITT TRIGGER", "TTL兼容CMOS": "TTL COMPATIBLE CMOS", "开漏": "OPEN DRAIN",
           "电平转换器": "LEVEL TRANSLATOR", "输入轨到轨": "RAIL TO RAIL INPUT", "OUTPUT RAIL TO RAIL": "RAIL TO RAIL OUTPUT",
           "COMPLEMENTARY TYPE": "COMPLEMENTARY"}


def _metin(v: str) -> str:
    """Büyük harf, tire = boşluk, '74HC Series' = '74HC', eşanlamlılar; liste değerleri sırasız ("A、B" = "B, A")."""
    parcalar = (re.sub(r"^(\d\w*) SERIES$", r"\1", re.sub(r"[\s-]+", " ", p).strip()) for p in re.split(r"[、,]", v.upper()))
    return " + ".join(sorted({ESANLAM.get(p, p) for p in parcalar if p}))


def _besleme(ozl: dict, kural: Kural):
    """Op-amp toplam besleme aralığı (V+ - V-) olarak (alt, üst); katalogda olmayan sınır None.
    Tek besleme "3V~32V"; çift besleme "-15V~-5V、5V~15V" (±5..±15 V = 10..30 V) ya da "±16V" (alt sınır yok)."""
    tek, cift, azami = (ozl.get(ad) or {} for ad in (kural.ozellik, *kural.diger))
    altlar, ustler = [], []
    if isinstance(tek.get("voltage min", [None])[0], SAYI) and isinstance(tek.get("voltage max", [None])[0], SAYI):
        altlar.append(tek["voltage min"][0])
        ustler.append(tek["voltage max"][0])
    v = cift.get("default", [""])[0]
    if isinstance(v, str) and len(parca := v.split("、")) == 2:
        s = [abs(float(x)) / (1000 if m else 1) for p in parca for x, m in HAM_GERILIM.findall(p)]
        if len(s) == 4 and s[0] == s[3] and s[1] == s[2]:  # yalnız simetrik "-b~-a、a~b"; başka biçim tahmin edilmez
            altlar.append(2 * min(s))
            ustler.append(2 * max(s))
    a, b = cift.get("voltage min", [None])[0], cift.get("voltage max", [None])[0]
    if isinstance(a, SAYI) and isinstance(b, SAYI) and a == -b:
        ustler.append(2 * b)
    if not ustler and isinstance(azami.get("voltage", [None])[0], SAYI):  # azami değer çoğu zaman mutlak sınır: son çare
        ustler.append(azami["voltage"][0])
    if not altlar and not ustler:
        return None
    return (min(altlar) if altlar else None, max(ustler) if ustler else None)


def _deger(ozl: dict, kural: Kural, ham: dict | None = None):
    if kural.ham:
        metin = (ham or {}).get(kural.ozellik, "")
        if kural.tur in ("esit", "icerir"):
            return _metin(metin) or None
        sayilar = [float(s) / (1000 if m else 1) for s, m in HAM_GERILIM.findall(metin)]
        return (min(sayilar), max(sayilar)) if sayilar else None
    if kural.tur == "besleme":
        return _besleme(ozl, kural)
    d = next((ozl[ad] for ad in (kural.ozellik, *kural.diger) if ozl.get(ad)), None)
    if not d:
        return None
    if kural.tur in ("kapsar", "icinde", "tolerans"):
        sayilar = [v[0] for v in d.values() if isinstance(v[0], SAYI)]
        return (min(sayilar), max(sayilar)) if sayilar else None
    if kural.anahtar:
        if kural.anahtar not in d:
            return None  # beklenen büyüklük yok: başka bir büyüklüğe (ör. akım yerine gerilim) geçilmez
        v = d[kural.anahtar][0]
    else:
        v = next(iter(d.values()))[0]
        if isinstance(v, str):  # "Rail-to-Rail Input, Rail-to-Rail Output" normalleştiricide iki anahtara bölünüyor
            v = "、".join(x[0] for x in d.values() if isinstance(x[0], str))
    if v == "NaN" or v is None:
        return None
    return _metin(v) if isinstance(v, str) else v


def _kosul(ozl: dict, kural: Kural):
    d = next((ozl[ad] for ad in (kural.ozellik, *kural.diger) if ozl.get(ad)), {})
    v = d.get(kural.kosul, [None])[0]
    return v if isinstance(v, SAYI) else None


def kural_uygula(kural: Kural, eski: dict, yeni: dict, ham_e: dict | None = None, ham_y: dict | None = None):
    """('tamam'|'zayif'|'ihlal'|'bilinmiyor', açıklama) ya da (iki tarafta da değer yoksa) None."""
    a, b = _deger(eski, kural, ham_e), _deger(yeni, kural, ham_y)
    if a is None:
        # Eskinin değeri yoksa adayın onu karşıladığı söylenemez.
        return ("bilinmiyor", f"{kural.etiket}: eski parçada değer yok, karşılaştırılamadı") if b is not None else None
    if b is None:
        return "bilinmiyor", f"{kural.etiket}: adayda değer yok"
    if kural.belirsiz:
        return "bilinmiyor", (f"{kural.etiket}: katalogda {_y(a)} / {_y(b)}, ama bu sayının {kural.belirsiz}; "
                              "datasheet'ten aynı koşulda karşılaştırın")
    kotu = "ihlal" if kural.zorunlu else "zayif"
    t = kural.tur
    if t in ("en_az", "en_cok"):
        if not isinstance(a, SAYI):
            return "bilinmiyor", f"{kural.etiket}: eski parçanın değeri okunamadı ({a})"
        if not isinstance(b, SAYI):
            return "bilinmiyor", f"{kural.etiket}: adayın değeri okunamadı ({b})"
        if kural.kosul:
            ka, kb = _kosul(eski, kural), _kosul(yeni, kural)
            if (ka is None) != (kb is None) or (ka is not None and abs(ka - kb) > 0.01 * max(abs(ka), abs(kb))):
                return "bilinmiyor", (f"{kural.etiket} farklı koşulda ölçülmüş ({_y(ka)} / {_y(kb)}); "
                                      "aynı koşulda datasheet'ten karşılaştırın")
        a, b = abs(a), abs(b)  # Ioh gibi işaretli değerlerde büyüklük karşılaştırılır
    if t == "esit":
        ok = abs(a - b) <= GORECELI * max(abs(a), abs(b), 1e-15) if isinstance(a, SAYI) and isinstance(b, SAYI) else a == b
        return ("tamam", "") if ok else (kotu, f"{kural.etiket}: {_y(a)} / {_y(b)}")
    if t == "icerir":  # aday eskinin her özelliğini taşımalı (rail-to-rail giriş+çıkış, çıkış yerine olmaz)
        ok = set(str(b).split(" + ")) >= set(str(a).split(" + "))
        return ("tamam", "") if ok else (kotu, f"{kural.etiket}: {_y(a)} / {_y(b)}")
    if t == "besleme":
        kotu_sinir = (a[0] is not None and b[0] is not None and b[0] > a[0]) or \
                     (a[1] is not None and b[1] is not None and b[1] < a[1])
        if kotu_sinir:
            return kotu, f"{kural.etiket} dar: {_y(a)} V / {_y(b)} V"
        if None in a or None in b:
            return "bilinmiyor", f"{kural.etiket}: {_y(a)} V / {_y(b)} V, bir sınır katalogda yok"
        return "tamam", ""
    if t == "en_az":
        return ("tamam", "") if b >= a * (1 - GORECELI) else (kotu, f"{kural.etiket} düşük: {_y(a)} / {_y(b)}")
    if t == "en_cok":
        return ("tamam", "") if b <= a * (1 + GORECELI) else (kotu, f"{kural.etiket} yüksek: {_y(a)} / {_y(b)}")
    if t == "kapsar":
        return ("tamam", "") if b[0] <= a[0] and b[1] >= a[1] else (kotu, f"{kural.etiket} dar: {_y(a)} / {_y(b)}")
    if t == "icinde":  # adayın aralığı eskisinin içinde (ör. zener: daha dar tolerans olur, daha geniş olmaz)
        return ("tamam", "") if b[0] >= a[0] and b[1] <= a[1] else (kotu, f"{kural.etiket} geniş: {_y(a)} / {_y(b)}")
    if t == "tolerans":
        return ("tamam", "") if max(map(abs, b)) <= max(map(abs, a)) + 1e-9 else (kotu, f"{kural.etiket} geniş: ±{_y(max(map(abs, a)))} / ±{_y(max(map(abs, b)))}")
    if t == "dielektrik":
        da, db = dielektrik(str(a)), dielektrik(str(b))
        if da is None or db is None:
            return ("tamam", "") if a == b else ("bilinmiyor", f"{kural.etiket}: {a} / {b} karşılaştırılamadı")
        ok = db[0] <= da[0] and db[1] >= da[1] and db[2] <= da[2]
        return ("tamam", "") if ok else (kotu, f"{kural.etiket} uygun değil: {a} ({da[0]}~{da[1]} °C, ±%{da[2]}) / "
                                               f"{b} ({db[0]}~{db[1]} °C, ±%{db[2]})")
    raise ValueError(t)


def _y(v):
    """Sayıyı kısa yazar (SI öneki)."""
    if isinstance(v, tuple):
        return f"{_y(v[0])}~{_y(v[1])}"
    if v is None:
        return "?"
    if not isinstance(v, (int, float)):
        return str(v)
    if v == 0:
        return "0"
    for carpan, onek in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")):
        if abs(v) >= carpan:
            return f"{v / carpan:.3g}{onek}"
    return f"{v:.3g}"


PIN_SAYILI = re.compile(r"^(?:SOIC|SOP|SSOP|TSSOP|HTSSOP|MSOP|VSSOP|ESOP|DIP|PDIP|QFN|DFN|SON|WSON|LQFP|TQFP|QFP|"
                        r"SOT-23|TSOT-23|SOT-89|TO-220|TO-263|SC-70)-(\d+)$")


def kilif_pin_sayisi(kk: str) -> int | None:
    """Adında pin sayısı taşıyan kılıflar için sayı (SOIC-8 -> 8); SOT-223, TO-252 gibi adlarda None."""
    m = PIN_SAYILI.match(kk)
    return int(m.group(1)) if m else None


# Ortak kılıf adı -> KiCad'deki lehim izi adları (sembollerin kılıf süzgeçleri bunlara uygulanır).
TEMSIL = {
    "SOIC-8": ["SOIC-8_3.9x4.9mm_P1.27mm", "SO8"], "SOIC-14": ["SOIC-14_3.9x8.7mm_P1.27mm", "SO14"],
    "SOIC-16": ["SOIC-16_3.9x9.9mm_P1.27mm", "SO16"], "SOT-23-3": ["SOT-23", "SOT-23-3"],
    "SOT-23-5": ["SOT-23-5"], "SOT-23-6": ["SOT-23-6"], "SOT-223": ["SOT-223-3_TabPin2"],
    "TO-220-3": ["TO-220-3_Vertical"], "TO-252": ["TO-252-2", "TO-252-3_TabPin2"],
    "TO-263": ["TO-263-2", "TO-263-3_TabPin2"], "SOT-89-3": ["SOT-89-3"], "SOT-323": ["SOT-323_SC-70"],
    "SMA": ["D_SMA"], "SMB": ["D_SMB"], "SMC": ["D_SMC"], "SOD-123": ["D_SOD-123"], "SOD-323": ["D_SOD-323"],
    "TO-92": ["TO-92_Inline"], "DIP-8": ["DIP-8_W7.62mm"], "TSSOP-8": ["TSSOP-8_4.4x3mm_P0.65mm"],
    "MSOP-8": ["MSOP-8_3x3mm_P0.65mm"], "TSSOP-14": ["TSSOP-14_4.4x5mm_P0.65mm"], "TSSOP-16": ["TSSOP-16_4.4x5mm_P0.65mm"],
}
# Önek eşleşmesinde artan kısım paket/ambalaj kodu gibi görünmeli: harfle başlar ya da -,/,# ve ardından harf.
# "-1", "-3.3" gibi rakamla başlayan ekler çoğu zaman işlev/gerilim sürümüdür (LTC6102-1, AMS1117-3.3): kabul edilmez.
AMBALAJ_EKI = re.compile(r"[A-Z][A-Z0-9/#.+-]{0,9}|[-/#][A-Z][A-Z0-9/#.+-]{0,8}")


class PinKaynagi:
    """Bir parçanın pin tablosunu KiCad ve EasyEDA'dan toplar, iki kaynağı karşılaştırır."""

    def __init__(self, easyeda_yolu: Path | None = None):
        with gzip.open(KOK / "kaynak" / "kicad_pinler.json.gz", "rt", encoding="utf-8") as f:
            self.kicad = json.load(f)
        # Taban ad -> semboller ("LM317" -> LM317_TO-220, LM317_SOT-223 ...; "AMS1117-3.3" -> kendisi).
        self.taban = defaultdict(list)
        for ad in self.kicad:
            self.taban[ad.upper()].append(ad)
            if "_" in ad:
                self.taban[ad.split("_")[0].upper()].append(ad)
        # Joker desenler ("XC6206PxxxMR"): sabit başlangıçlarının ilk 3 harfine göre dizinlenir.
        self.desen = defaultdict(list)
        for ad in self.kicad:
            if "x" in ad and ad.upper() != ad:
                self.desen[ad.upper()[:3]].append((re.compile("^" + re.escape(ad).replace("x", "[A-Z0-9.]") + "$"), ad))
        self.easyeda = onbellek_oku(easyeda_yolu) if easyeda_yolu else onbellek_oku()
        self._on = {}

    def _uygun(self, ad: str, kk: str) -> bool:
        """Sembolün kılıfı ve pin sayısı parçayla tutuyor mu."""
        sembol = self.kicad[ad]
        temsil = TEMSIL.get(kk, [])
        if sembol["fp"]:
            fp = sembol["fp"].split(":")[-1]
            kilif_ok = fp in temsil or kilif_k(re.sub(r"^(D|R|C|L)_", "", fp).split("_")[0]) == kk
        else:
            kilif_ok = any(fnmatch(t.upper(), f.upper()) for f in sembol["filtre"].split() for t in temsil)
        kpin = kilif_pin_sayisi(kk)
        pinsay = max((int(p) for p in sembol["pinler"] if p.isdigit()), default=0)
        return kilif_ok and (kpin is None or kpin == pinsay)

    def kicad_bul(self, mpn: str, kk: str) -> str | None:
        r = self.kicad_esle(mpn, kk)
        return r[0] if r else None

    def kicad_esle(self, mpn: str, kk: str) -> tuple[str, str] | None:
        """(sembol adı, önek eşleşmesinde artan ek). Tam ad ya da joker desen eşleşmesinde ek boştur."""
        m = re.sub(r"\(.*?\)$", "", mpn.strip()).upper()
        isimler = [m] + ([re.sub(r"^(SN|MC|MM|HD|NLV|M)(?=74)", "", m)] if re.match(r"^(SN|MC|MM|HD|NLV|M)74", m) else [])
        for isim in isimler:
            onekler = [isim] + [isim[:n] for n in range(len(isim) - 1, 3, -1) if AMBALAJ_EKI.fullmatch(isim[n:])]
            for onek in onekler:  # tam ad, sonra joker desen ("XC6206PxxxMR"), sonra bir kısa önek
                for taban in [onek] + [ad.upper() for desen, ad in self.desen.get(onek[:3], []) if desen.match(onek)]:
                    for ad in self.taban.get(taban, []):
                        if self._uygun(ad, kk):
                            return ad, isim[len(onek):]
        return None

    def bul(self, lcsc: str, mpn: str, kk: str, aile: str, uretici: str | None = None) -> dict:
        """Pin tablosu ve güven düzeyi:
        iki kaynak    KiCad ile EasyEDA uyuşuyor
        parcaya ozel  yalnız EasyEDA (her LCSC parçası için ayrı çizilmiş sembol)
        kicad uretici yalnız KiCad; sembolün datasheet'i parçanın üreticisine ait
        kicad ad      yalnız KiCad, yalnız parça adına göre (sembol başka üreticinin dizilimini gösterebilir)
        celiski       KiCad ile EasyEDA uyuşmuyor
        yok           pin verisi yok"""
        if lcsc in self._on:
            return self._on[lcsc]
        e = self.easyeda.get(lcsc)
        e_pin = e["pinler"] if e and e.get("durum") == "var" and e.get("pinler") else None
        es = self.kicad_esle(mpn, kk) if aile in PIN_AILELERI else None
        ks, ek = es if es else (None, "")
        k_pin = self.kicad[ks]["pinler"] if ks else None
        if e_pin and k_pin:
            uyum = karsilastir(k_pin, e_pin, aile)["sonuc"]
            sonuc = {"pinler": e_pin, "kaynak": "KiCad + EasyEDA", "guven": "iki kaynak" if uyum in ("uyumlu", "notlu") else "celiski"}
            if sonuc["guven"] == "celiski":
                sonuc["kicad_pinler"] = k_pin
        elif e_pin:
            sonuc = {"pinler": e_pin, "kaynak": "EasyEDA", "guven": "parcaya ozel"}
        elif k_pin:
            # Tek harfli ek çoğu zaman işlev farkıdır (BAT54 -> BAT54S seri, LM317 -> LM317L düşük akım): güçlü sayılmaz.
            ayni = uretici_tutar(self.kicad[ks].get("ds", ""), uretici) and len(ek) != 1
            sonuc = {"pinler": k_pin, "kaynak": "KiCad", "guven": "kicad uretici" if ayni else "kicad ad"}
        else:
            sonuc = {"pinler": None, "kaynak": None, "guven": "yok"}
        sonuc["kicad"] = ks
        if ks:
            sonuc["kicad_ds"] = alan_adi(self.kicad[ks].get("ds", ""))
        self._on[lcsc] = sonuc
        return sonuc


# KiCad sembolünün datasheet alan adı -> o üreticinin JLC'deki adında geçen ifadeler.
# Kısa adlar ("ST", "TI") kasıtlı yok: JLC'de "ST(Semtech)" gibi başka markalar var.
URETICI_ALANI = {
    "ti.com": ["texas instruments"], "st.com": ["stmicroelectronics"], "microchip.com": ["microchip", "atmel", "micrel"],
    "analog.com": ["analog devices", "linear technology", "maxim"], "maximintegrated.com": ["maxim", "analog devices"],
    "onsemi.com": ["onsemi", "on semiconductor", "fairchild"], "fairchildsemi.com": ["fairchild", "onsemi"],
    "nxp.com": ["nxp", "nexperia"], "nexperia.com": ["nexperia", "nxp"], "vishay.com": ["vishay"],
    "infineon.com": ["infineon", "international rectifier"], "irf.com": ["international rectifier", "infineon"],
    "diodes.com": ["diodes inc", "diodes incorporated", "zetex"], "torexsemi.com": ["torex"],
    "aosmd.com": ["alpha & omega", "alpha and omega"], "advanced-monolithic.com": ["advanced monolithic"],
    "rohm.com": ["rohm"], "toshiba.semicon-storage.com": ["toshiba"], "toshiba.co.jp": ["toshiba"], "renesas.com": ["renesas", "intersil"], "intersil.com": ["intersil", "renesas"],
    "silabs.com": ["silicon lab"], "allegromicro.com": ["allegro"], "littelfuse.com": ["littelfuse"],
    "power.com": ["power integrations"], "powerint.com": ["power integrations"], "skyworksinc.com": ["skyworks"],
    "broadcom.com": ["broadcom", "avago"], "diotec.com": ["diotec"], "kemet.com": ["kemet"], "murata.com": ["murata"],
    "cypress.com": ["cypress", "infineon"], "akm.com": ["asahi kasei", "akm"], "richtek.com": ["richtek"],
    "monolithicpower.com": ["monolithic power"], "semtech.com": ["semtech corp"], "wolfspeed.com": ["wolfspeed", "cree"],
}


def alan_adi(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1).lower().removeprefix("www.") if m else ""


def uretici_tutar(ds_url: str, uretici: str | None) -> bool:
    """KiCad sembolünün datasheet'i bu üreticiye mi ait? Bilinmeyen alan adında False (temkinli)."""
    alan, ad = alan_adi(ds_url), (uretici or "").lower()
    for anahtar, adlar in URETICI_ALANI.items():
        if alan == anahtar or alan.endswith("." + anahtar):  # yalnız üreticinin kendi alanı ya da alt alanı
            return any(a in ad for a in adlar)
    return False


GUCLU_PIN = {"iki kaynak", "parcaya ozel", "kicad uretici"}


def degerlendir(eski: dict, aday: dict, pk: PinKaynagi | None) -> dict:
    """eski/aday: katalog satırı sözlüğü (ozellik çözülmüş). Sınıf + kanıt döndürür."""
    aile = eski["aile"]
    notlar, eksik, ihlal, bilgi = [], [], [], []
    for ozellik in TEMEL.get(aile, []):
        if ozellik not in eski["ozl"] or ozellik not in aday["ozl"]:
            eksik.append(f"Temel değer eksik: {ozellik} ({'eski parçada' if ozellik not in eski['ozl'] else 'adayda'} yok)")
    alt = eski.get("alt") or ""
    for kural in KURALLAR.get(aile, []):
        if not kural.uygulanir(alt):
            continue
        s = kural_uygula(kural, eski["ozl"], aday["ozl"], eski.get("ham"), aday.get("ham"))
        if s is None:
            if kural.zorunlu:  # iki tarafta da yok: başarı sayılmaz
                eksik.append(f"{kural.etiket}: iki parçada da değer yok, doğrulanamadı")
            continue
        durum, aciklama = s
        if durum == "ihlal":
            ihlal.append(aciklama)
        elif durum == "zayif":
            notlar.append(aciklama)
        elif durum == "bilinmiyor":
            (eksik if kural.zorunlu else bilgi).append(aciklama)

    ayni_kilif = eski["kilif_k"] == aday["kilif_k"]
    pin = None
    if aile in PINSIZ:
        pin_durum = "tanim" if ayni_kilif else "farkli_kilif"
    else:
        pa = pk.bul(eski["lcsc"], eski["mpn"], eski["kilif_k"], aile, eski.get("uretici")) if pk else {"pinler": None, "guven": "yok"}
        pb = pk.bul(aday["lcsc"], aday["mpn"], aday["kilif_k"], aile, aday.get("uretici")) if pk else {"pinler": None, "guven": "yok"}
        if pa["pinler"] and pb["pinler"]:
            pin = karsilastir(pa["pinler"], pb["pinler"], aile)
            pin_durum = pin["sonuc"]
            if "celiski" in (pa["guven"], pb["guven"]):
                pin_durum = "celiski"
            elif not {pa["guven"], pb["guven"]} <= GUCLU_PIN:
                # Ada göre KiCad tablosu başka üreticinin dizilimi olabilir: kesin hüküm verilmez.
                eksik.append("Pin tablosu yalnız parça adına göre (KiCad, başka üreticinin sembolü); "
                             "bu üreticinin dizilimi doğrulanmadı" + (" ve tablo uyumsuz görünüyor" if pin_durum == "uyumsuz" else ""))
                pin_durum = "zayif"
        else:
            pin_durum = "veri_yok"
        pin = {"sonuc": pin_durum, "eski": pa.get("kaynak"), "yeni": pb.get("kaynak"),
               "guven": [pa["guven"], pb["guven"]], "satirlar": (pin or {}).get("satirlar", [])}

    if ihlal or pin_durum == "uyumsuz":
        sinif = "uygun_degil"
        if pin_durum == "uyumsuz":
            ihlal.insert(0, "Pin dizilimi uyumsuz")
    elif not ayni_kilif:
        sinif = "farkli_kilif"
    elif pin_durum in ("veri_yok", "celiski", "belirsiz", "zayif") or eksik:
        sinif = "kontrol"
    elif notlar or bilgi or pin_durum == "notlu":  # doğrulanamayan değer de "doğrudan"ı engeller
        sinif = "farkli"
    else:
        sinif = "dogrudan"
    return {"sinif": sinif, "ihlal": ihlal, "eksik": eksik, "notlar": notlar, "bilgi": bilgi, "pin": pin}
