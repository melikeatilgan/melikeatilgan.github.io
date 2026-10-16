# melikeatilgan.github.io

Kişisel sitemin ve **Muadil** aracının kaynak kodu. Site: <https://melikeatilgan.github.io>

## Muadil: komponent muadil bulucu

Bir kartta kullanılan parça bulunamadığında ya da üretimden kalktığında yerine takılabilecek parçayı arıyor.
Bir parça numarası (ya da LCSC kodu) yazınca:

1. parçayı birebir buluyor; yazılan kodu sessizce başka bir koda çevirmiyor,
2. aynı kategorideki adayları kılıf, pin dizilimi ve elektriksel değerlerle karşılaştırıyor,
3. her adayı beş sınıftan birine koyuyor ve nedenini yazıyor:
   **doğrudan takılır**, **takılır ama farkları var**, **kontrol gerekli**, **farklı kılıf**, **uygun değil**.

Araç: <https://melikeatilgan.github.io/muadil/> · Yöntem: <https://melikeatilgan.github.io/muadil/nasil.html>

**BOM risk raporu** (<https://melikeatilgan.github.io/muadil/bom.html>): bir kartın parça listesi (düz liste ya da
JLCPCB BOM CSV'si) verilince katalogda olmayan, stoğu düşük, JLCPCB'de ek montaj ücreti çıkaran ve doğrulanmış
muadili olmayan (tek kaynak) parçaları tek tabloda işaretliyor. Dosya tarayıcıdan çıkmıyor. Örnek liste:
<https://melikeatilgan.github.io/muadil/bom.html?ornek>

### Pin dizilimi neden ayrıca kontrol ediliyor?

Aynı kılıf aynı pin dizilimi demek değil. KiCad kütüphanesinde SOT-23 kılıflı LDO'lar için dört ayrı dizilim var:

| Pin | XC6206 | AP7381 | APE8865 | LM3480 |
|---|---|---|---|---|
| 1 | GND | IN | OUT | OUT |
| 2 | OUT | OUT | GND | IN |
| 3 | IN | GND | IN | GND |

Pin tablosu iki kaynaktan geliyor: KiCad'in resmî sembol kütüphanesi ve LCSC'nin EasyEDA sembolleri. İki kaynak
uyuşuyorsa "iki kaynakla doğrulandı" yazıyor. Pin tablosu olmayan, kaynakları çelişen ya da tablosu yalnız parça adına
göre bulunan (KiCad sembolü başka üreticinin) bir parça için "doğrudan takılır" denmiyor.

Neden üretici önemli: Torex'in XC6206P332MR'ında SOT-23 dizilimi 1 VSS, 2 VOUT, 3 VIN; UMW'nin aynı numaralı parçasının
datasheet'inde 1 GND, 2 Input, 3 Output. Aynı parça numarası, ters giriş-çıkış.

## Nasıl çalışıyor

Sunucu yok; site tamamen statik ve GitHub Pages'te duruyor. Veri her gün GitHub Actions ile yenileniyor:

```
JLCPCB stoklu katalog taraması  (muadil/jlc.py)        ~725 bin parça
        |
Katalog veritabanı              (muadil/katalog.py)     özellikler birimli sayıya çevrilir
        |
Pin verisi                      (muadil/kicad.py, muadil/easyeda.py, muadil/pinler.py)
        |
Muadil kuralları                (muadil/eslestir.py)    aile başına zorunlu / tercih kuralları
        |
Statik site verisi              (muadil/yayinla.py)     sıkıştırılmış JSON dosyaları
```

Testler geçmezse ya da tarama eksik kalırsa yayın yapılmıyor; site son sağlam haliyle kalıyor.

## Klasörler

| Klasör | İçerik |
|---|---|
| `muadil/` | Python kodu: tarama, katalog, pin karşılaştırma, kurallar, dışa aktarma |
| `kaynak/` | Depoda tutulan veri: KiCad pin tablosu, EasyEDA pin önbelleği |
| `site/` | Ana sayfa ve aracın arayüzü (HTML, CSS, JavaScript) |
| `tests/` | Altın testler: 7805/7905 ve SOT-23 LDO tuzakları, klon parçalar, kanal eşleme, kurallar |

## Yerelde çalıştırma

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
python -m pytest -q
python -m muadil.jlc tara          # katalog taraması, ~30 dakika
python -m muadil.katalog           # veri/katalog.db
python -m muadil.yayinla           # site/muadil/veri/
python -m http.server 8000 --directory site
```

KiCad pin tablosunu yeniden üretmek için: `python -m muadil.kicad "<KiCad>/share/kicad/symbols"`.

## Veri kaynakları ve lisanslar

- Parça kataloğu, fiyat ve stok: JLCPCB / LCSC.
- `kaynak/kicad_pinler.json.gz`: KiCad sembol kütüphanesinden türetildi, CC-BY-SA 4.0.
- `kaynak/easyeda.jsonl`: LCSC / EasyEDA sembollerinden pin ve ped bilgisi.
- Özellik normalleştirme: [jlcparts](https://github.com/yaqwsx/jlcparts) (MIT).
- Kod: MIT (`LICENSE`).

## Sınırlar

- Katalog JLCPCB'nin stoklu parçalarıyla sınırlı.
- Kılıf uyumu kılıf adıyla karşılaştırılıyor; aynı adlı kılıflarda ped ölçüleri biraz farklı olabilir.
- Yaşam durumu (üretimden kalkma), otomotiv ve askerî kalifikasyon bilgisi bu veride yok.
- Sonuçlar karar destek için; seri üretimden önce datasheet ile doğrulanmalı.
