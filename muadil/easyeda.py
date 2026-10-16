"""EasyEDA / LCSC sembol ve lehim izi verisi.

Her LCSC parçası için pin numarası + adı ve footprint pedleri buradan gelir. Uç anahtarsızdır
ama sıkı hız sınırı vardır (~15-20 istekten sonra geçici 403). Bu yüzden:
- iki ayna sırayla kullanılır, 403 alan ayna bir süre dinlendirilir,
- sonuçlar kalıcı önbelleğe yazılır (pin dizilimi değişmez), aynı parça bir daha sorulmaz.
"""
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AYNALAR = ["https://easyeda.com", "https://lceda.cn"]
AJAN = "muadil/0.1"
ONBELLEK = Path(__file__).resolve().parent.parent / "kaynak" / "easyeda.jsonl"
MM = 0.254  # EasyEDA tuval birimi 10 mil


def ayristir(yanit: dict) -> dict:
    """API yanıtını {pinler: {no: [ad, birim]}, kilif, pedler: [[no, x, y, g, y, şekil]]} yapar."""
    if not yanit.get("success"):
        return {"durum": "yok"}
    s = yanit["result"]
    parcalar = [(0, s["dataStr"])] + [(i + 1, p["dataStr"]) for i, p in enumerate(s.get("subparts") or [])]
    pinler = {}
    for birim, ds in parcalar:
        for sekil in ds.get("shape", []):
            if not sekil.startswith("P~"):
                continue
            bolum = sekil.split("^^")
            no = bolum[0].split("~")[3].strip()
            ad = bolum[3].split("~")[4].strip() if len(bolum) > 3 else ""
            pinler.setdefault(no, [ad, birim])
    paket = s.get("packageDetail") or {}
    pedler = []
    for sekil in (paket.get("dataStr") or {}).get("shape", []):
        if sekil.startswith("PAD~"):
            a = sekil.split("~")
            # PAD~şekil~x~y~en~boy~katman~net~no~...
            pedler.append([a[8], round(float(a[2]) * MM, 3), round(float(a[3]) * MM, 3),
                           round(float(a[4]) * MM, 3), round(float(a[5]) * MM, 3), a[1]])
    return {"durum": "var", "pinler": pinler, "kilif": paket.get("title", ""), "pedler": pedler}


class Getirici:
    """Kibar getirici: aynaları sırayla dener, 403 alanı artan sürelerle dinlendirir."""

    def __init__(self, aralik: float = 4.0):
        self.aralik = aralik
        self.dinlen = {a: 0.0 for a in AYNALAR}
        self.ceza = {a: 600.0 for a in AYNALAR}
        self.son = 0.0

    def getir(self, lcsc: str) -> dict | None:
        """Ayrıştırılmış kayıt ya da (hiçbir ayna hazır değilse) None döndürür."""
        for ayna in AYNALAR:
            if time.time() < self.dinlen[ayna]:
                continue
            time.sleep(max(0.0, self.son + self.aralik - time.time()))
            self.son = time.time()
            try:
                istek = urllib.request.Request(
                    f"{ayna}/api/products/{lcsc}/components?version=6.4.19.5", headers={"User-Agent": AJAN})
                with urllib.request.urlopen(istek, timeout=30) as y:
                    self.ceza[ayna] = 600.0
                    return ayristir(json.loads(y.read()))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {"durum": "yok"}
                self.dinlen[ayna] = time.time() + self.ceza[ayna]
                self.ceza[ayna] = min(self.ceza[ayna] * 2, 7200)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                self.dinlen[ayna] = time.time() + 120
        return None

    def hazir_bekle(self):
        time.sleep(max(1.0, min(self.dinlen.values()) - time.time()))


def onbellek_oku(yol: Path = ONBELLEK) -> dict:
    kayitlar = {}
    if yol.exists():
        with open(yol, encoding="utf-8") as f:
            for satir in f:
                try:
                    k = json.loads(satir)
                except json.JSONDecodeError:  # yazılırken okunan yarım son satır
                    continue
                kayitlar[k["lcsc"]] = k
    return kayitlar


def tara(kodlar: list[str], yol: Path = ONBELLEK, sinir_sn: float = 8 * 3600, aralik: float = 4.0):
    """Önbellekte olmayan kodları sırayla getirir ve her birini hemen dosyaya ekler."""
    bilinen = onbellek_oku(yol)
    g = Getirici(aralik)
    bas = time.time()
    yeni = 0
    with open(yol, "a", encoding="utf-8") as f:
        for kod in kodlar:
            if kod in bilinen:
                continue
            while (k := g.getir(kod)) is None:
                if time.time() - bas > sinir_sn:
                    return yeni
                g.hazir_bekle()
            k["lcsc"] = kod
            k["tarih"] = time.strftime("%Y-%m-%d")
            f.write(json.dumps(k, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            yeni += 1
            if yeni % 50 == 0:
                print(f"{yeni} yeni ({time.time() - bas:.0f} sn)", flush=True)
            if time.time() - bas > sinir_sn:
                break
    return yeni


def birlestir(ek: Path, yol: Path = ONBELLEK) -> int:
    """Başka bir önbellek dosyasındaki kayıtları ekler (aynı parça tekrar yazılmaz)."""
    kayitlar = {**onbellek_oku(ek), **onbellek_oku(yol)}
    satirlar = (json.dumps(k, ensure_ascii=False, separators=(",", ":")) for k in kayitlar.values())
    yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return len(kayitlar)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["birlestir"]:
        print("kayıt:", birlestir(Path(sys.argv[2])))
    elif sys.argv[1:2] == ["tara"]:
        kodlar = Path(sys.argv[2]).read_text(encoding="utf-8").split()
        print("yeni kayıt:", tara(kodlar, sinir_sn=float(sys.argv[3]) if len(sys.argv) > 3 else 8 * 3600))
    else:
        for yol in sys.argv[1:]:
            k = ayristir(json.loads(Path(yol).read_text(encoding="utf-8")))
            print(Path(yol).stem, k.get("kilif"), k.get("pinler"), len(k.get("pedler", [])))
