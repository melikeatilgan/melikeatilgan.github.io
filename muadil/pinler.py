"""Pin adlarını ortak işleve çevirir ve iki parçanın pin dizilimini karşılaştırır.

Kaynaklar farklı adlar kullanır (VIN / VI / IN / INPUT, "IN A+" / "1IN+" / "+IN1"...).
Her ad, parçanın ailesine göre bir rol ve (varsa) kanal numarasına çevrilir.
Çok kanallı parçalarda (çift op-amp, dörtlü kapı) kanal numaraları kaynaklar arasında farklı
olabilir; bu yüzden kanalların bire bir eşlenip eşlenmediğine bakılır, numaranın kendisine değil.
"""
import re
import unicodedata

KANAL_HARF = {"A": 1, "B": 2, "C": 3, "D": 4}
BOS = {"NC", "N.C.", "N.C", "N/C", "NIC", "NU"}
DNC = {"DNC", "DONOTCONNECT"}  # "bağlama": NC'den farklı, karttaki ped bir hatta bağlıysa sorun çıkar
BILINMIYOR = "?"  # yalnız numaradan oluşan ad ("1", "2"): işlev bilgisi taşımaz

ORTAK = {
    "GND": "GND", "VSS": "GND", "COM": "GND", "COMMON": "GND", "0V": "GND", "AGND": "GND", "PGND": "GND",
    "GROUND": "GND",
}
REGULATOR = {
    **ORTAK,
    "VIN": "IN", "VI": "IN", "IN": "IN", "INPUT": "IN", "VCC": "IN", "VDD": "IN", "V+": "IN",
    "VOUT": "OUT", "VO": "OUT", "OUT": "OUT", "OUTPUT": "OUT",
    "ADJ": "ADJ", "FB": "ADJ", "ADJ/FB": "ADJ", "ADJUST": "ADJ", "ADJUSTMENT": "ADJ",
    "EN": "EN", "CE": "EN", "ENABLE": "EN", "ON/OFF": "EN", "ON": "EN", "EN/UVLO": "EN+UVLO",
    # Kutbu addan anlaşılmayan kapatma pinleri: EasyEDA üst çizgi göstermez, çoğu LDO'da SHDN etkin-düşüktür.
    "SHDN": "SHDN", "SD": "SHDN", "INH": "SHDN", "SHUTDOWN": "SHDN",
    "BYP": "BYP", "BP": "BYP", "BYPASS": "BYP", "NR": "BYP", "NR/SS": "BYP+SS", "SS/NR": "BYP+SS",
    "PG": "PG", "PGOOD": "PG", "POK": "PG", "PWRGD": "PG", "PGD": "PG",
    "TAB": "TAB", "EP": "TAB", "EPAD": "TAB", "PAD": "TAB", "THERMALPAD": "TAB",
}
OPAMP_GUC = {"V+": "V+", "VCC": "V+", "VDD": "V+", "+VS": "V+", "VS+": "V+", "+V": "V+", "VCC+": "V+", "VDD+": "V+",
             "V-": "V-", "VEE": "V-", "-VS": "V-", "VS-": "V-", "-V": "V-", "VCC-": "V-",
             "GND": "V-", "VSS": "V-"}
TRANSISTOR = {"G": "G", "GATE": "G", "S": "S", "SOURCE": "S", "D": "D", "DRAIN": "D",
              "B": "B", "BASE": "B", "C": "C", "COLLECTOR": "C", "E": "E", "EMITTER": "E",
              "TAB": "TAB", "EP": "TAB", "PAD": "TAB"}
DIYOT = {"A": "A", "ANODE": "A", "+": "A", "K": "K", "C": "K", "CATHODE": "K", "KATHODE": "K", "-": "K"}
ZAMANLAYICI = {
    **ORTAK, "VCC": "VCC", "VDD": "VCC", "V+": "VCC",
    "TRIG": "TRIG", "TR": "TRIG", "TRIGGER": "TRIG", "OUT": "OUT", "Q": "OUT", "OUTPUT": "OUT",
    "RST": "RST", "RESET": "RST", "R": "RST", "CONT": "CONT", "CV": "CONT", "CTRL": "CONT", "CONTROL": "CONT",
    "THRES": "THR", "THR": "THR", "TH": "THR", "THRESHOLD": "THR",
    "DISCH": "DIS", "DIS": "DIS", "DISCHARGE": "DIS", "DC": "DIS",
}

AILELER = {
    "regulator": REGULATOR, "opamp": OPAMP_GUC, "transistor": TRANSISTOR,
    "diyot": DIYOT, "zamanlayici": ZAMANLAYICI, "lojik": ORTAK, "genel": ORTAK,
}


def temizle(ad: str) -> str:
    a = unicodedata.normalize("NFKC", ad).strip().upper().replace("−", "-").replace("–", "-")
    a = re.sub(r"~\{([^}]*)\}", r"\1", a)  # KiCad üst çizgisi (etkin düşük işareti)
    a = re.sub(r"\((.*?)\)", r"/\1", a)     # "ADJ(GND)" -> "ADJ/GND"
    return a.replace(" ", "").replace("_", "").strip("/")


def eslesir(a: str, b: str) -> bool:
    """Roller ortak bir işlev taşıyor mu ('ADJ|GND' ile 'GND' eşleşir).
    KiCad'in adsız lojik girişi ("IN") harfli girişlerin (IN_A, IN_B) hepsiyle eşleşir; harfliler kendi aralarında eşleşmez."""
    ka, kb = set(a.split("|")), set(b.split("|"))
    if ka & kb:
        return True
    return ("IN" in ka and any(x.startswith("IN_") for x in kb)) or ("IN" in kb and any(x.startswith("IN_") for x in ka))


def _opamp(a: str, tip: str, birim: int):
    """Op-amp/karşılaştırıcı pini: (rol, kanal). Ör. '1IN+', 'IN A-', '-IN1', 'OUTB', ''+output."""
    if a in OPAMP_GUC:
        return OPAMP_GUC[a], None
    if "/" in a and all(p in OPAMP_GUC for p in a.split("/")):  # "VEE/GND"
        return "|".join(dict.fromkeys(OPAMP_GUC[p] for p in a.split("/"))), None
    m = re.fullmatch(r"(NEG|POS)/?(\d)", a) or re.fullmatch(r"IN([A-D1-4])([NP])", a)  # "NEG/1", "INAN"
    if m:
        kanal_s, isaret = (m.group(2), "-" if m.group(1) == "NEG" else "+") if m.group(1) in ("NEG", "POS")             else (m.group(1), "-" if m.group(2) == "N" else "+")
        return "IN" + isaret, KANAL_HARF.get(kanal_s) or int(kanal_s)
    isaret = "+" if "+" in a else "-" if "-" in a else ""
    govde = a.replace("+", "").replace("-", "").replace("/", "")  # "OUT/A", "-IN/A"
    for anahtar, rol in (("VOUT", "OUT"), ("OUTPUT", "OUT"), ("OUT", "OUT"), ("VIN", "IN"), ("INPUTS", "IN"),
                         ("INPUT", "IN"), ("IN", "IN")):
        if anahtar in govde:
            kalan = govde.replace(anahtar, "", 1)
            break
    else:
        if govde == "" and isaret:            # KiCad: "+" / "-"
            rol, kalan = "IN", ""
        elif govde == "" and tip == "output":  # KiCad: adsız çıkış
            rol, kalan = "OUT", ""
        else:
            return a, None
    if kalan and kalan not in KANAL_HARF and not kalan.isdigit():
        return a, None
    kanal = KANAL_HARF.get(kalan) or (int(kalan) if kalan.isdigit() else birim or 1)
    return rol + isaret, kanal


def _lojik(a: str, tip: str, birim: int):
    """74xx kapı pini: '1A' / 'A1' / '1Y' ya da KiCad'de adsız giriş/çıkış + birim."""
    if a in ORTAK:
        return ORTAK[a], None
    if a in ("VCC", "VDD"):
        return "VCC", None
    if a == "" and tip in ("input", "output"):
        return ("IN" if tip == "input" else "OUT"), birim or 1
    m = re.fullmatch(r"(\d+)([A-Z]+)|([A-Z]+)(\d+)", a)
    if m:
        harf, kanal = (m.group(2), m.group(1)) if m.group(1) else (m.group(3), m.group(4))
        if harf in ("Y", "Q", "O"):
            return "OUT", int(kanal)
        if harf in ("A", "B", "C", "D", "I"):
            return "IN_" + harf, int(kanal)  # mux gibi parçalarda A ile B yer değiştiremez
        return harf, int(kanal)
    return a, None


def rol(ad: str, aile: str, tip: str = "", birim: int = 0):
    """(rol, kanal) döndürür; kanal yalnız çok kanallı ailelerde dolu olur."""
    ham = unicodedata.normalize("NFKC", ad).strip().upper()
    dusuk = bool(re.fullmatch(r"~\{.*\}", ham)) or ham.endswith("#")  # üst çizgi ya da # = etkin düşük
    a = temizle(ad).rstrip("#")
    if a in BOS or (a == "" and tip == "no_connect"):
        return "NC", None
    if a in DNC:
        return "DNC", None
    if a.isdigit():
        return BILINMIYOR, None
    if aile == "regulator" and dusuk:
        if a in ("SHDN", "SD", "SHUTDOWN"):
            return "EN", None   # etkin-düşük kapatma = yüksekte açık = EN
        if a in ("EN", "CE", "ENABLE"):
            return "ENB", None  # etkin-düşük etkinleştirme: EN'in tersi
    if aile == "opamp":
        r = _opamp(a, tip, birim)
    elif aile == "lojik":
        r = _lojik(a, tip, birim)
        if dusuk and r[0] not in ("", "GND", "VCC"):  # Q ile Q̄ ayrı kalsın (flip-flop çıkışları)
            r = (r[0] + "_N", r[1])
    else:
        r = None
    if r is not None:
        return (BILINMIYOR, None) if r[0] == "" else r  # adsız ve tipinden de çözülemeyen pin
    if a == "":
        return BILINMIYOR, None  # adsız pin (ör. KiCad'de BAT54A/C): işlev bilinmiyor, "eşleşti" sayılmaz
    tablo = AILELER.get(aile, ORTAK)
    if a in tablo:
        return tablo[a], None
    # "GND/ADJ", "VOUT/TAB" gibi birleşik adlar: tanınan her parça alternatif işlev olur.
    parcalar = [tablo.get(p, p) for p in a.split("/") if p]
    return "|".join(dict.fromkeys(parcalar)) or a, None


# NC ile başka bir rolün karşılaşması: (eski, yeni) -> (durum, not)
NC_KURALI = {
    ("NC", "BYP"): ("uyari", "Yeni parçanın BYP pini boşta kalır; çoğu üründe isteğe bağlıdır, gürültü artabilir."),
    ("BYP", "NC"): ("uyari", "Karttaki baypas kondansatörü NC pine bağlı kalır; zararsızdır."),
    ("NC", "PG"): ("uyari", "Yeni parçanın PG çıkışı boşta kalır; zararsızdır."),
    ("PG", "NC"): ("uyari", "Karttaki PG hattı artık sinyal almaz."),
    ("EN", "NC"): ("uyari", "EN denetimi kaybolur; yeni parça hep açık çalışır."),
    ("ADJ", "NC"): ("hata", "Karttaki ayar direnci NC pine bağlı kalır; çıkış ayarlanamaz."),
}


def _kanal_eslesir(ciftler) -> bool:
    """Kanal numaraları bire bir eşlenebiliyor mu (A->1, B->2 ya da A->2, B->1 da olur)."""
    ileri, geri = {}, {}
    for a, b in ciftler:
        if a is None or b is None:
            continue
        if ileri.setdefault(a, b) != b or geri.setdefault(b, a) != a:
            return False
    return True


def karsilastir(eski: dict, yeni: dict, aile: str) -> dict:
    """eski/yeni: {no: [ad, tip, birim]} ya da {no: [ad, birim]} (EasyEDA).
    Dönen: {"sonuc": uyumlu|notlu|uyumsuz|belirsiz, "satirlar": [...], "notlar": [...]}"""
    def r(p):
        ad, tip, birim = (p[0], p[1], p[2]) if len(p) == 3 else (p[0], "", p[1])
        return rol(ad, aile, tip, birim)

    re_ = {no: r(p) for no, p in eski.items()}
    ry = {no: r(p) for no, p in yeni.items()}
    satirlar, notlar, kanallar = [], [], []
    for no in sorted(set(re_) | set(ry), key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else 0, n)):
        a, b = re_.get(no), ry.get(no)
        ad_a = eski[no][0] if no in eski else None
        ad_b = yeni[no][0] if no in yeni else None
        if a is None or b is None:
            var = a or b
            taraf, karsi = (ry, re_) if a is None else (re_, ry)  # pinin olduğu taraf, olmadığı taraf
            ayni_taraf = {r for n2, x in taraf.items() if n2 != no for r in x[0].split("|")}
            karsi_roller = {r for x in karsi.values() for r in x[0].split("|")} - {BILINMIYOR}
            en_buyuk = max((int(n) for n in karsi if n.isdigit()), default=0)
            ek_pin = no.isdigit() and int(no) > en_buyuk  # karşı paketin pinlerinin ötesinde: SOT-223 tabı gibi
            # Kabul: NC/TAB ya da (ek pin ve aynı taraftaki başka bir pinin işlevini taşıyor ve o işlev karşıda da var)
            if var[0] != BILINMIYOR and (eslesir(var[0], "NC|TAB")
                                         or (ek_pin and set(var[0].split("|")) & ayni_taraf & karsi_roller)):
                durum, aciklama = "tamam", "Pin yalnız bir tarafta; NC ya da gövde/tab ile aynı işlev."
            else:
                durum, aciklama = "belirsiz", "Pin yalnız bir tarafta var; öbür kaynakta bu pinin bilgisi yok."
        elif BILINMIYOR in (a[0], b[0]):
            durum, aciklama = "belirsiz", "Pin adı yalnız numara; işlevi kaynakta yazmıyor."
        elif eslesir(a[0], b[0]):
            durum, aciklama = "tamam", ""
            kanallar.append((a[1], b[1]))
        elif "DNC" in (a[0], b[0]):
            durum, aciklama = "belirsiz", "DNC (bağlama) pini: karttaki ped bir hatta bağlıysa sorun çıkar; kartı kontrol edin."
        elif (a[0], b[0]) in NC_KURALI:
            durum, aciklama = NC_KURALI[(a[0], b[0])]
        elif "NC" in (a[0], b[0]):
            durum = "hata" if a[0] == "NC" else "uyari"
            aciklama = ("Eski kartta boş olan pin yeni parçada " + b[0] + " işlevinde." if a[0] == "NC"
                        else a[0] + " işlevi yeni parçada yok (NC).")
        elif "TAB" in (a[0], b[0]):
            # Tab, aynı parçada "VOUT(TAB)" gibi tab'a bağlı yazılan pinin işlevini taşır.
            taraf, diger_rol = (re_, b[0]) if a[0] == "TAB" else (ry, a[0])
            tab_rolleri = {r for x in taraf.values() if "TAB" in x[0].split("|")
                           for r in x[0].split("|") if r != "TAB"}
            if tab_rolleri & set(diger_rol.split("|")):
                durum, aciklama = "tamam", "Tab, " + "/".join(sorted(tab_rolleri)) + " ile aynı düğüm."
            elif not tab_rolleri:
                durum, aciklama = "uyari", "Tab'ın bağlı olduğu düğüm belirtilmemiş; datasheet ile doğrulayın."
            else:
                durum, aciklama = "hata", f"Tab farklı düğümde: {a[0]} / {b[0]}."
        elif any("+" in r and set(r.split("+")) & set(o.split("|")) for r, o in ((a[0], b[0]), (b[0], a[0]))):
            durum, aciklama = "belirsiz", f"Ek işlevli pin ({a[0]} / {b[0]}): ek işlev (UVLO, soft-start) kartta kullanılıyorsa datasheet'e bakın."
        elif {a[0], b[0]} == {"EN", "ENB"}:
            durum, aciklama = "hata", "Etkinleştirme mantığı ters: biri yüksekte, öteki düşükte açar."
        elif {a[0], b[0]} & {"SHDN"} and {a[0], b[0]} & {"EN", "ENB"}:
            durum, aciklama = "belirsiz", ("Etkinleştirme pini adı farklı (EN / SHDN). SHDN çoğu üründe etkin-düşüktür ve EN "
                                          "ile aynı çalışır, ama kutbu datasheet'ten doğrulanmalı.")
        else:
            durum, aciklama = "hata", f"İşlev farklı: {a[0]} / {b[0]}."
        satirlar.append({"no": no, "eski": ad_a, "yeni": ad_b,
                         "rol_eski": a and a[0], "rol_yeni": b and b[0], "durum": durum, "aciklama": aciklama})
    if not _kanal_eslesir(kanallar):
        notlar.append("Kanal pinleri karışık: bir kanalın girişleri ile çıkışı yeni parçada farklı kanallara düşüyor.")
        sonuc = "uyumsuz"
    else:
        durumlar = {s["durum"] for s in satirlar}
        sonuc = ("uyumsuz" if "hata" in durumlar else "belirsiz" if "belirsiz" in durumlar
                 else "notlu" if "uyari" in durumlar else "uyumlu")
    return {"sonuc": sonuc, "satirlar": satirlar, "notlar": notlar}
