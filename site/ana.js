// Ana sayfa etkileşimleri: kart üzerindeki numaralı notlar ve "Aynı kılıf, farklı bacak" kutusu.
const h = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// --- Kart notları: numaraya ya da listedeki satıra basınca ikisi birlikte seçilir ---
const noktalar = [...document.querySelectorAll(".nokta")];
const notlar = [...document.querySelectorAll(".notlar li")];
function notSec(n) {
  const acik = noktalar.find((b) => b.dataset.not === n)?.getAttribute("aria-pressed") === "true";
  noktalar.forEach((b) => b.setAttribute("aria-pressed", String(!acik && b.dataset.not === n)));
  notlar.forEach((li) => li.classList.toggle("secili", !acik && li.id === "not-" + n));
}
noktalar.forEach((b) => b.addEventListener("click", () => notSec(b.dataset.not)));
notlar.forEach((li) => li.addEventListener("click", () => notSec(li.id.slice(4))));

// --- Kart seçici: ana kart, sensör başlığı, telemetri geçidi ---
const sekmeler = [...document.querySelectorAll('[role="tab"]')];
function sekmeSec(secilen) {
  notSec(""); // açık not varsa kapanır
  for (const s of sekmeler) {
    const acik = s === secilen, ad = s.id.slice(6);
    s.setAttribute("aria-selected", String(acik));
    s.tabIndex = acik ? 0 : -1;
    document.getElementById("panel-" + ad).hidden = !acik;
    document.getElementById("notlar-" + ad).hidden = !acik;
  }
  document.getElementById("kart-alt").textContent = secilen.dataset.alt;
}
sekmeler.forEach((s, i) => {
  s.addEventListener("click", () => sekmeSec(s));
  s.addEventListener("keydown", (e) => {
    const yon = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!yon) return;
    const yeni = sekmeler[(i + yon + sekmeler.length) % sekmeler.length];
    sekmeSec(yeni);
    yeni.focus();
  });
});

// --- Aynı kılıf, farklı bacak ---
// Renk sınıfı: g giriş/kontrol, c çıkış, t toprak/ortak uç, a ayar, x diğer.
function rol(ad) {
  const a = ad.toUpperCase();
  if (/^(GND|VSS|E|S)$/.test(a)) return "t";
  if (/^(VI|IN|VIN|INPUT|B|G)$/.test(a)) return "g";
  if (/^(VO|OUT|VOUT|OUTPUT|C|D)$/.test(a)) return "c";
  if (a.startsWith("ADJ")) return "a";
  return "x";
}

// Sabit kılıf çizimleri (çizim alanı x 80..280, y 0..210). pinler: [no, numara x, numara y, ad x, ad y]; tab varsa ikinci pinin adı tabın üstüne de yazılır.
const SABIT = {
  sot23: {
    yon: "üstten görünüş",
    sekil: '<rect class="govde" x="125" y="75" width="110" height="60" rx="4"/><rect class="bacak" x="139" y="135" width="22" height="22"/><rect class="bacak" x="199" y="135" width="22" height="22"/><rect class="bacak" x="169" y="53" width="22" height="22"/>',
    pinler: [[1, 150, 150, 150, 182], [2, 210, 150, 210, 182], [3, 180, 68, 180, 40]],
  },
  sot223: {
    yon: "üstten görünüş · tab = pin 2",
    sekil: '<rect class="bacak" x="135" y="44" width="90" height="31" rx="2"/><rect class="govde" x="105" y="75" width="150" height="62" rx="4"/><rect class="bacak" x="131" y="137" width="18" height="22"/><rect class="bacak" x="171" y="137" width="18" height="22"/><rect class="bacak" x="211" y="137" width="18" height="22"/>',
    pinler: [[1, 140, 152, 140, 184], [2, 180, 152, 180, 184], [3, 220, 152, 220, 184]], tab: [180, 34],
  },
  sot89: {
    yon: "üstten görünüş · tab = pin 2",
    sekil: '<rect class="bacak" x="160" y="46" width="40" height="30" rx="2"/><rect class="govde" x="120" y="75" width="120" height="58" rx="4"/><rect class="bacak" x="136" y="133" width="18" height="22"/><rect class="bacak" x="171" y="133" width="18" height="22"/><rect class="bacak" x="206" y="133" width="18" height="22"/>',
    pinler: [[1, 145, 148, 145, 182], [2, 180, 148, 180, 182], [3, 215, 148, 215, 182]], tab: [180, 36],
  },
  to92: {
    yon: "önden görünüş, düz yüz size dönük",
    sekil: '<path class="govde" d="M132 128V64a48 30 0 0 1 96 0v64z"/><rect class="bacak" x="151" y="128" width="8" height="34"/><rect class="bacak" x="176" y="128" width="8" height="34"/><rect class="bacak" x="201" y="128" width="8" height="34"/>',
    pinler: [[1, 155, 170, 155, 200], [2, 180, 170, 180, 200], [3, 205, 170, 205, 200]],
  },
  to220: {
    yon: "önden görünüş, yazılı yüz size dönük",
    sekil: '<rect class="bacak" x="134" y="10" width="92" height="44" rx="2"/><circle cx="180" cy="31" r="10" fill="var(--yuzey)"/><rect class="govde" x="130" y="54" width="100" height="74" rx="3"/><rect class="bacak" x="150" y="128" width="10" height="34"/><rect class="bacak" x="175" y="128" width="10" height="34"/><rect class="bacak" x="200" y="128" width="10" height="34"/>',
    pinler: [[1, 155, 170, 155, 200], [2, 180, 170, 180, 200], [3, 205, 170, 205, 200]],
  },
};

// SOT-23-5/6: 1-2-3 altta soldan sağa, kalanlar üstte sağdan sola.
function sotCok(n) {
  let sekil = '<rect class="govde" x="105" y="75" width="150" height="60" rx="4"/>';
  const pinler = [];
  [130, 180, 230].forEach((x, i) => { sekil += `<rect class="bacak" x="${x - 9}" y="135" width="18" height="22"/>`; pinler.push([i + 1, x, 150, x, 184]); });
  (n === 5 ? [230, 130] : [230, 180, 130]).forEach((x, j) => { sekil += `<rect class="bacak" x="${x - 9}" y="53" width="18" height="22"/>`; pinler.push([4 + j, x, 68, x, 40]); });
  return { yon: "üstten görünüş", sekil, pinler };
}

// İki sıralı kılıf (DIP, SOIC, TSSOP): solda 1..n/2 yukarıdan aşağı, sağda kalanlar aşağıdan yukarı.
function cift(n, etiket, renk, baslik) {
  const ad = 22, yar = n / 2, H = 40 + yar * ad;
  let s = `<rect class="govde" x="120" y="12" width="80" height="${H - 24}" rx="4"/><path d="M150 12a10 10 0 0 0 20 0" fill="var(--yuzey)" stroke="#3a424e" stroke-width="1.5"/>`;
  for (let i = 0; i < n; i++) {
    const sol = i < yar, y = 31 + (sol ? i : n - 1 - i) * ad;
    s += `<rect class="bacak ${renk ? renk[i] : ""}" x="${sol ? 106 : 200}" y="${y - 5}" width="14" height="10">${baslik ? `<title>${h(baslik(i))}</title>` : ""}</rect>`;
    s += `<text class="kno" x="${sol ? 125 : 195}" y="${y + 3.5}" text-anchor="${sol ? "start" : "end"}">${i + 1}</text>`;
    if (etiket) s += `<text class="ad kucuk-ad r-${rol(etiket[i])}" x="${sol ? 100 : 220}" y="${y + 4.5}" text-anchor="${sol ? "end" : "start"}">${h(etiket[i])}</text>`;
  }
  return { kutu: `0 0 320 ${H}`, s };
}

// Dört kenarlı kılıf (QFP, QFN): pin 1 sol kenarın üstünde, saat yönünün tersine.
function dort(n, renk, baslik) {
  const k = n / 4, p = 10, S = (k + 2) * p, m = 30, L = 12, W = S + 2 * m;
  let s = `<rect class="govde" x="${m}" y="${m}" width="${S}" height="${S}" rx="3"/><circle cx="${m + 11}" cy="${m + 11}" r="4" fill="var(--soluk)"/>`;
  for (let i = 0; i < n; i++) {
    const t = m + 1.5 * p + (i % k) * p, ters = W - t;
    const [x, y, w, yk] = [[m - L, t - 3, L, 6], [t - 3, m + S, 6, L], [m + S, ters - 3, L, 6], [ters - 3, m - L, 6, L]][Math.floor(i / k)];
    s += `<rect class="bacak ${renk[i]}" x="${x}" y="${y}" width="${w}" height="${yk}"><title>${h(baslik(i))}</title></rect>`;
  }
  const yaz = (metin, x, y, a) => `<text class="kno" x="${x}" y="${y}" text-anchor="${a}">${metin}</text>`;
  s += yaz(1, m - L - 3, m + 1.5 * p + 3, "end") + yaz(k + 1, m + 1.5 * p, m + S + L + 11, "middle")
     + yaz(2 * k + 1, m + S + L + 3, W - m - 1.5 * p + 3, "start") + yaz(3 * k + 1, W - m - 1.5 * p, m - L - 4, "middle");
  return { kutu: `0 0 ${W} ${W}`, s };
}

// BGA: satırlar harf, sütunlar sayı; A1 sol üstte.
function bga(toplar, renk, baslik) {
  const harf = (t) => t.match(/^[A-Z]+/)[0], sayi = (t) => +t.match(/\d+$/)[0];
  const satirlar = [...new Set(toplar.map(harf))], kolon = Math.max(...toplar.map(sayi));
  const c = 14, m = 24, W = m + kolon * c + 6, H = m + satirlar.length * c + 6;
  let s = `<rect class="govde" x="${m - 4}" y="${m - 4}" width="${kolon * c + 8}" height="${satirlar.length * c + 8}" rx="3"/>`;
  satirlar.forEach((r, i) => { s += `<text class="kno" font-size="10" x="${m - 8}" y="${m + i * c + c / 2 + 3}" text-anchor="end">${r}</text>`; });
  for (let j = 1; j <= kolon; j++) if (kolon <= 16 || j % 2) s += `<text class="kno" font-size="10" x="${m + (j - 1) * c + c / 2}" y="${m - 8}" text-anchor="middle">${j}</text>`;
  toplar.forEach((t, i) => {
    s += `<circle class="bacak ${renk[i]}" cx="${m + (sayi(t) - 1) * c + c / 2}" cy="${m + satirlar.indexOf(harf(t)) * c + c / 2}" r="5"><title>${h(baslik(i))}</title></circle>`;
  });
  return { kutu: `0 0 ${W} ${H}`, s };
}

const tip = (o) => o.cizim.split("-")[0];

// Az bacaklı kılıf: seçili parçanın pin adları çizimde, bütün parçalar tabloda.
function kucukCizim(o, secili) {
  const p = o.parcalar[secili];
  const aria = `aria-label="${h(o.kilif)} kılıfında ${h(p.ad)} pinleri: ${p.pin.map((a, i) => `${i + 1} ${h(a)}`).join(", ")}"`;
  if (tip(o) === "cift") {
    const c = cift(p.pin.length, p.pin);
    return { yon: "üstten görünüş", svg: `<svg class="pin-cizim genis" viewBox="${c.kutu}" role="img" ${aria}>${c.s}</svg>` };
  }
  const k = SABIT[o.cizim] || sotCok(p.pin.length);
  const numara = (no, x, y) => `<circle cx="${x}" cy="${y}" r="9" fill="var(--yazi)"/><text class="no" x="${x}" y="${y + 4}" text-anchor="middle">${no}</text>`;
  const ad = (metin, x, y) => `<text class="ad r-${rol(metin)}" x="${x}" y="${y}" text-anchor="middle">${h(metin)}</text>`;
  let s = k.sekil;
  for (const [no, nx, ny, ax, ay] of k.pinler) s += numara(no, nx, ny) + ad(p.pin[no - 1], ax, ay);
  if (k.tab) s += ad(p.pin[1], k.tab[0], k.tab[1]);
  return { yon: k.yon, svg: `<svg class="pin-cizim" viewBox="80 0 200 210" role="img" ${aria}>${s}</svg>` };
}

function tabloGorunum(o, secili) {
  const c = kucukCizim(o, secili);
  const bas = o.parcalar.map((p, j) => `<th><button type="button" data-parca="${j}" aria-pressed="${j === secili}">${h(p.ad)}</button></th>`).join("");
  const satirlar = o.parcalar[0].pin.map((_, n) =>
    `<tr><td>${n + 1}</td>${o.parcalar.map((p) => `<td class="r-${rol(p.pin[n])}">${h(p.pin[n])}</td>`).join("")}</tr>`).join("");
  return `<div class="pin-ikili"><div><p class="pin-gorunus">${h(o.parcalar[secili].ad)} · ${h(c.yon)}</p>${c.svg}</div>
    <table><thead><tr><th>Pin</th>${bas}</tr></thead><tbody>${satirlar}</tbody></table></div>
    <p class="pin-alt">Çizimi değiştirmek için parça adına basın. Kaynak: ${h(o.kaynak)}.</p>`;
}

// Çok bacaklı kılıf: iki parça karşılaştırılır, farklı pinler kırmızı. GND ile VSS aynı sayılır.
const esitAd = (a, b) => { const n = (x) => (x.toUpperCase() === "VSS" ? "GND" : x.toUpperCase()); return n(a) === n(b); };
function farkGorunum(o) {
  const [A, B] = o.parcalar, n = A.pin.length, birim = o.toplar ? "top" : "pin";
  const no = (i) => (o.toplar ? o.toplar[i] : String(i + 1));
  const renk = A.pin.map((a, i) => (esitAd(a, B.pin[i]) ? "ayni" : "farkli"));
  const baslik = (i) => `${o.toplar ? "Top" : "Pin"} ${no(i)}: ${A.pin[i]} / ${B.pin[i]}`;
  const c = tip(o) === "bga" ? bga(o.toplar, renk, baslik) : tip(o) === "dort" ? dort(n, renk, baslik) : cift(n, null, renk, baslik);
  const farklar = [...Array(n).keys()].filter((i) => renk[i] === "farkli");
  const satir = (i) => `<tr><td>${h(no(i))}</td><td>${h(A.pin[i])}</td><td>${h(B.pin[i])}</td></tr>`;
  const ilk = farklar.slice(0, 8), kalan = farklar.slice(8);
  return `<div class="pin-ikili"><div><p class="pin-gorunus">${h(A.ad)} ↔ ${h(B.ad)} · üstten görünüş${o.toplar ? ", A1 sol üstte" : ""}</p>
    <svg class="pin-cizim genis" viewBox="${c.kutu}" role="img" aria-label="${h(o.kilif)} kılıfında ${h(A.ad)} ile ${h(B.ad)}: ${n} ${birim} içinden ${farklar.length} tanesi farklı">${c.s}</svg>
    <p class="pin-lejant"><span class="k ayni"></span>aynı<span class="k farkli"></span>farklı<button type="button" class="pin-buyut">Büyüt</button></p></div>
    <div><p class="pin-ozet"><strong>${farklar.length}</strong> / ${n} ${birim} farklı</p>
    <table><thead><tr><th>${o.toplar ? "Top" : "Pin"}</th><th>${h(A.ad)}</th><th>${h(B.ad)}</th></tr></thead><tbody>${ilk.map(satir).join("")}</tbody></table>
    ${kalan.length ? `<details><summary>Kalan ${kalan.length} farklı ${birim}</summary><table><tbody>${kalan.map(satir).join("")}</tbody></table></details>` : ""}</div></div>
    <p class="pin-alt">Bir pinin üstüne gelince iki parçadaki adı görünür. Kaynak: ${h(o.kaynak)}.</p>`;
}

const kutu = document.getElementById("pin");
const COK = 12; // daha çok bacakta iki parçanın farkı gösterilir; üç parçalı uzun tablo ekrana sığmıyor
const rastgele = (n) => Math.floor(Math.random() * n);
const karistir = (a) => a.map((x) => [Math.random(), x]).sort((p, q) => p[0] - q[0]).map((x) => x[1]);
let DIZIN = null, simdiki = null;
const havuzlar = new Map();
const havuzAl = (id) => {
  if (!havuzlar.has(id)) havuzlar.set(id, fetch(`pin/${id}.json`).then((y) => (y.ok ? y.json() : Promise.reject(new Error(y.status))))
    .catch((e) => { havuzlar.delete(id); throw e; })); // ağ düzelince yeniden denensin
  return havuzlar.get(id);
};

// Dörtte bir seçilmiş örnek; kalanında bir kılıf havuzundan farklı dizilimli rastgele parçalar.
async function yeniOrnek() {
  const { secilmis, havuzlar: liste } = DIZIN;
  if (Math.random() < 0.25) return secilmis[rastgele(secilmis.length)];
  const agirlik = liste.map((x) => Math.sqrt(x.sembol)); // büyük havuz daha sık, küçükler de ara sıra
  let r = Math.random() * agirlik.reduce((a, b) => a + b);
  const secim = liste.find((_, i) => (r -= agirlik[i]) < 0) || liste[0];
  const hv = await havuzAl(secim.id);
  const desen = karistir(hv.desenler).slice(0, hv.desenler[0].pin.length > COK ? 2 : 3);
  return {
    kilif: hv.kilif, cizim: hv.cizim, toplar: hv.toplar, kaynak: "KiCad 10 sembol kütüphanesi",
    tur: [hv.ayrinti, `KiCad'de bu kılıfı kullanan ${hv.sembol} sembol, ${hv.dizilim} farklı dizilim`].filter(Boolean).join(" · "),
    parcalar: desen.map((d) => ({ ad: d.adlar[rastgele(d.adlar.length)], pin: d.pin })),
  };
}

function goster(o, secili = 0) {
  simdiki = o;
  const govde = o.parcalar[0].pin.length > COK ? farkGorunum(o) : tabloGorunum(o, secili);
  kutu.innerHTML = `
    <div class="pin-bas"><span class="mono">AYNI KILIF, FARKLI BACAK</span><button type="button" id="pin-yeni">Başka örnek ↻</button></div>
    <p class="pin-kilif">${h(o.kilif)}</p>
    <p class="pin-tur">${h(o.tur)}</p>
    ${govde}`;
}

async function yenile(odak) {
  const dugme = document.getElementById("pin-yeni");
  if (dugme) { dugme.disabled = true; dugme.textContent = "Yükleniyor…"; }
  try {
    goster(await yeniOrnek());
  } catch {
    goster(DIZIN.secilmis[rastgele(DIZIN.secilmis.length)]); // havuz dosyası gelmezse seçilmiş örnek
  }
  if (odak) document.getElementById("pin-yeni").focus();
}

if (kutu) {
  const buyuk = document.getElementById("pin-buyuk");
  buyuk.addEventListener("click", (e) => { if (e.target === buyuk || e.target.closest(".pin-kapat")) buyuk.close(); }); // dış alana basınca da kapanır
  fetch("pin/dizin.json").then((y) => y.json()).then((d) => { DIZIN = d; return yenile(false); })
    .catch(() => {}); // veri gelmezse sayfadaki sabit örnek kalır
  kutu.addEventListener("click", (e) => {
    const parca = e.target.closest("[data-parca]");
    if (parca && simdiki) { goster(simdiki, Number(parca.dataset.parca)); kutu.querySelector(`[data-parca="${parca.dataset.parca}"]`)?.focus(); return; }
    if (e.target.closest("#pin-yeni") && DIZIN) yenile(true);
    if (e.target.closest(".pin-buyut")) {
      const d = document.getElementById("pin-buyuk");
      d.querySelector(".pin-buyuk-ic").innerHTML = kutu.querySelector(".pin-cizim").outerHTML;
      d.showModal();
    }
  });
}

const $ = (id) => document.getElementById(id);
const virgul = (x, b = 1) => x.toFixed(b).replace(".", ",");
const azHareket = matchMedia("(prefers-reduced-motion: reduce)").matches;

// --- Motor: izleme kartının karar mantığı. Eşikler ve teyit süreleri kartın tasarım belgesindeki karar tablosundan
// (03-donanim-v4, blok diyagram bölüm 7) ve cep kartından; In = 28,3 A (WEG W22 15 kW). ---
const motor = $("motor");
if (motor) {
  const IN = 28.3, ALAN = ["l1", "l2", "l3", "titresim", "de", "nde", "yanband", "yalitim"];
  const NORMAL = { l1: 26.2, l2: 26.6, l3: 25.9, titresim: 1.6, de: 62, nde: 58, yanband: -60, yalitim: 120, ptc: "normal" };
  const PTC_AD = { normal: "Normal", atti: "Attı", kopru: "Köprülenmiş", kopuk: "Kablo kopuk" };
  // Panel zamanı gerçeğin 10 katı hızlı akar; teyit süreleri belgedeki gibi. Yan bant ölçüm aralığı belgede yok, örnek 20 s.
  const HIZ = 10, YANBAND_ARALIK = 20;
  // Senaryo: [gerçek saniye, değişen değerler]; aradaki değerler doğrusal geçer, PTC adım adım değişir.
  const SENARYO = {
    rulman: [[0, {}], [3, { titresim: 2.6, de: 70 }], [6, { titresim: 3.6, de: 79, yanband: -58 }], [9, { titresim: 4.3, de: 87 }], [11, { titresim: 4.9, de: 93 }], [14, { titresim: 5.6, de: 102 }]],
    faz: [[0, {}], [2, {}], [2.4, { l3: 0, l1: 44.9, l2: 45.6, titresim: 2.4 }], [5, { l3: 0, l1: 45.2, l2: 45.9, titresim: 2.6 }]],
    yuk: [[0, {}], [4, { l1: 30.1, l2: 30.6, l3: 29.8, de: 66 }], [8, { l1: 32.4, l2: 32.9, l3: 32.1, de: 71 }], [12, { l1: 33.6, l2: 34.1, l3: 33.2, de: 74 }], [13, { ptc: "atti" }]],
    rotor: [[0, {}], [4, { yanband: -52, titresim: 1.9 }], [8, { yanband: -46, titresim: 2.2, l1: 26.9 }], [11, { yanband: -42, titresim: 2.4, l1: 27.4, l2: 26.1 }], [16, { yanband: -40, titresim: 2.5 }]],
    nem: [[0, {}], [3, { yalitim: 60 }], [6, { yalitim: 14 }], [9, { yalitim: 3 }]],
    normal: [[0, {}]],
  };
  let ptc = "normal", kilit = "", senaryo = null, simSaat = 0, raf = 0, sonT = 0;
  const ilk = new Map(); // koşul -> eşiğin ilk aşıldığı panel zamanı; eşiğin altına inince silinir, sayaç baştan başlar
  const deger = (k) => Number($("m-" + k).value);
  const hap = (id, metin, renk) => { const e = $(id); e.textContent = metin; e.style.setProperty("--hap", renk); };
  const YESIL = "#86c9a3", MAVI = "#8fb8e8", SARI = "#d9ad4f", KIRMIZI = "#ef8a78", TURUNCU = "#ec9b5e";
  const sureYaz = (s) => (s < 60 ? `${Math.floor(s)} s` : `${Math.floor(s / 60)} dk${s % 60 >= 1 ? ` ${Math.floor(s % 60)} s` : ""}`);

  function ptcSec(p) {
    ptc = p;
    document.querySelectorAll("#m-ptc button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.p === p)));
  }

  // Ölçümlerden eşiği aşan koşullar: kesme ya da uyarı, kanalı ve belgedeki teyit süresiyle.
  function kosullar() {
    const L = [deger("l1"), deger("l2"), deger("l3")], v = deger("titresim"), yb = deger("yanband"), r = deger("yalitim");
    const ort = (L[0] + L[1] + L[2]) / 3, enb = Math.max(...L);
    const denge = ort > 1 ? (100 * Math.max(...L.map((x) => Math.abs(x - ort)))) / ort : 0; // cep kartındaki formül
    const fazKaybi = ort > 3 && Math.min(...L) < 0.15 * ort;
    const k = [];
    const ekle = (anahtar, kanal, tur, ne, sure, teyitAd, not = "") => k.push({ anahtar, kanal, tur, ne, sure, teyitAd, not });
    if (fazKaybi) ekle("faz", "akim", "kes", "Faz kaybı", 2, "2 s", "kalan fazlar ≈ 1,73 × akım çeker, termik röle geç yakalar");
    if (v > 4.5) ekle("tit-k", "titresim", "kes", `Titreşim ${virgul(v)} mm/s, bölge D`, 10, "10 s");
    if (v > 2.8) ekle("tit-u", "titresim", "uyari", `Titreşim ${virgul(v)} mm/s, bölge ${v > 4.5 ? "D" : "C"}`, 10, "10 s");
    for (const [ad, kk] of [["DE", "de"], ["NDE", "nde"]]) {
      const t = deger(kk);
      if (t >= 100) ekle(kk + "-k", "yatak", "kes", `Yatak sıcaklığı ${ad} ${t} °C`, 60, "60 s", "gres bozunmadan önce");
      if (t >= 90) ekle(kk + "-u", "yatak", "uyari", `Yatak sıcaklığı ${ad} ${t} °C`, 60, "60 s");
    }
    if (ptc === "atti") ekle("ptc", "ptc", "kes", "PTC attı: sargı aşırı ısındı", 0, "anında", "motorun kendi koruması");
    if (ptc === "kopru") ekle("ptc-b", "ptc", "uyari", "PTC köprülenmiş: sargı koruması devre dışı", 0, "anında", "kesmez, motor sağlam");
    if (ptc === "kopuk") ekle("ptc-c", "ptc", "uyari", "PTC kablosu kopuk", 0, "anında", "kesmez");
    if (!fazKaybi && enb > IN * 1.1) ekle("akim", "akim", "uyari", `Faz akımı ${virgul(enb)} A, 31,1 A üstünde`, 300, "5 dk", "kesmez, aşırı akım termik rölenin işi");
    if (!fazKaybi && denge > 10) ekle("denge", "akim", "uyari", `Akım dengesizliği %${Math.round(denge)}`, 60, "60 s");
    if (yb > -45) ekle("yb", "yanband", "uyari", `Rotor çubuğu yan bandı ${yb} dB`, 3 * YANBAND_ARALIK, "3 ölçüm", "yavaş gelişir, planlı bakım konusu");
    return { L, ort, enb, denge, fazKaybi, v, yb, r, k };
  }

  // Teyit: koşul, süresi boyunca kesintisiz sürerse geçerli olur.
  function teyit(o) {
    const aktif = new Set(), s = { kes: [], uyari: [], bekleyen: [] };
    for (const c of o.k) {
      aktif.add(c.anahtar);
      if (!ilk.has(c.anahtar)) ilk.set(c.anahtar, simSaat);
      c.gecen = simSaat - ilk.get(c.anahtar);
      (c.gecen >= c.sure ? s[c.tur] : s.bekleyen).push(c);
    }
    for (const a of [...ilk.keys()]) if (!aktif.has(a)) ilk.delete(a);
    // aynı kanalda kesme varsa o kanalın uyarısı ayrıca yazılmaz
    const kesKanal = new Set([...s.kes, ...s.bekleyen.filter((c) => c.tur === "kes")].map((c) => c.kanal));
    s.bekleyen = s.bekleyen.filter((c) => c.tur === "kes" || !kesKanal.has(c.kanal));
    s.uyari = s.uyari.filter((c) => !s.kes.some((x) => x.kanal === c.kanal));
    return s;
  }

  // Kanal kartı: durum etiketi ve çerçeve rengi (kes kırmızı, uyarı sarı).
  const kanal = (ad, durum, metin, renk) => { $("k-" + ad).dataset.durum = durum; hap(`m-${ad}-h`, metin, renk); };
  const renkli = (id, metin, renk) => { const e = $(id); e.textContent = metin; e.style.color = renk || ""; };

  function yaz() {
    const o = kosullar(), t = teyit(o);
    ["l1", "l2", "l3"].forEach((k, i) => renkli(`m-${k}-y`, virgul(o.L[i]), o.fazKaybi && o.L[i] < 0.15 * o.ort ? KIRMIZI : o.L[i] > IN * 1.1 ? SARI : ""));
    $("m-akim-ozet").innerHTML = `Ortalama <b>${virgul(o.ort)} A</b> · dengesizlik <b>%${Math.round(o.denge)}</b><br>31,1 A (1,10 × In) ya da %10 üstü uyarı`;
    if (o.fazKaybi) kanal("akim", "kes", "faz kaybı", KIRMIZI);
    else if (o.enb > IN * 1.1) kanal("akim", "uyari", "aşırı akım", SARI);
    else if (o.denge > 10) kanal("akim", "uyari", "dengesiz", SARI);
    else kanal("akim", "", "normal", YESIL);
    $("m-titresim-y").textContent = virgul(o.v);
    const bolge = o.v <= 1.4 ? ["A", YESIL, ""] : o.v <= 2.8 ? ["B", MAVI, ""] : o.v <= 4.5 ? ["C", SARI, "uyari"] : ["D", KIRMIZI, "kes"];
    kanal("titresim", bolge[2], "Bölge " + bolge[0], bolge[1]);
    const tRenk = (x) => (x >= 100 ? KIRMIZI : x >= 90 ? SARI : "");
    for (const k of ["de", "nde"]) renkli(`m-${k}-y`, deger(k), tRenk(deger(k)));
    const tMax = Math.max(deger("de"), deger("nde"));
    kanal("yatak", tMax >= 100 ? "kes" : tMax >= 90 ? "uyari" : "", tMax >= 100 ? "kes" : tMax >= 90 ? "uyarı" : "normal", tRenk(tMax) || YESIL);
    kanal("ptc", ptc === "atti" ? "kes" : ptc === "kopru" || ptc === "kopuk" ? "uyari" : "", PTC_AD[ptc],
      ptc === "atti" ? KIRMIZI : ptc === "kopru" || ptc === "kopuk" ? SARI : YESIL);
    $("m-yanband-y").textContent = o.yb;
    kanal("yanband", o.yb > -45 ? "uyari" : "", o.yb > -45 ? "uyarı" : "normal", o.yb > -45 ? SARI : YESIL);
    $("m-yalitim-y").textContent = virgul(o.r, 0);
    kanal("yalitim", o.r < 5 ? "kes" : "", o.r < 5 ? "çalıştırma" : o.r < 20 ? "düşük" : "yeterli", o.r < 5 ? KIRMIZI : o.r < 20 ? MAVI : YESIL);

    // Kesme kilitlenir: sebep geçse de kendiliğinden kapanmaz. Motor durduğu için senaryo da durur, ölçümler kesme anında kalır.
    if (t.kes.length && !kilit) {
      kilit = t.kes[0].ne;
      if (senaryo) { $("m-saat").textContent = `kesme anı · +${Math.round(simSaat - senaryo.bas)} s`; senaryo = null; }
    }
    $("m-role").textContent = kilit ? "Röle bıraktı · motor durduruldu · kilitli" : "Röle çekili · çalışma izni var";
    $("m-role-lamba").classList.toggle("kesik", !!kilit);
    const kesBekliyor = t.bekleyen.some((c) => c.tur === "kes");
    let baslik, aciklama, renk;
    if (kilit) [baslik, aciklama, renk] = ["KESİLDİ", `Kesme nedeni: ${kilit}. ` + (o.k.some((c) => c.tur === "kes")
      ? "Sebep giderilip elle sıfırlanmadan motor tekrar çalışmaz." : "Sebep giderildi; kilit elle sıfırlanınca motor yeniden çalışabilir."), KIRMIZI];
    else if (o.r < 5) [baslik, aciklama, renk] = ["ÇALIŞTIRMA", "Yalıtım 5 MΩ altında (cep kartı): duran motor yeniden çalıştırılmaz; sebep bulunup ölçüm tekrarlanır.", KIRMIZI];
    else if (kesBekliyor) [baslik, aciklama, renk] = ["KESME TEYİDİ", "Kesme eşiği aşıldı. Teyit süresi boyunca sürerse röle bırakır; eşiğin altına inerse sayaç sıfırlanır.", TURUNCU];
    else if (t.uyari.length >= 2) [baslik, aciklama, renk] = ["ÖNCELİKLİ İŞ EMRİ", "Birden fazla uyarı birlikte. Kart kesmez, ama müdahale öne alınır.", TURUNCU];
    else if (t.uyari.length) [baslik, aciklama, renk] = ["UYARI · İŞ EMRİ", "Motor çalışmaya devam eder; bakım ekibi uyarılır, planlı müdahale açılır.", SARI];
    else [baslik, aciklama, renk] = ["NORMAL", t.bekleyen.length ? "Uyarı eşiği aşıldı; teyit süresi doluyor." : "Bütün kanallar sınırların içinde; ölçümler kaydediliyor.", YESIL];
    $("m-karar").style.setProperty("--karar", renk);
    $("m-karar-baslik").textContent = baslik;
    $("m-karar-aciklama").textContent = aciklama;
    const satir = (c, sinif, etiket, ek) => `<li class="${sinif}"><b>${etiket}</b> ${h(c.ne)}<span>${h(ek)}</span></li>`;
    $("m-karar-neden").innerHTML = [
      ...t.kes.map((c) => satir(c, "kes", "KES", [`${c.teyitAd} teyit`, c.not].filter(Boolean).join(" · "))),
      ...t.uyari.map((c) => satir(c, "uyari", "UYARI", [`${c.teyitAd} teyit`, c.not].filter(Boolean).join(" · "))),
      ...t.bekleyen.map((c) => satir(c, "teyit", "TEYİT", c.anahtar === "yb"
        ? `${Math.floor(c.gecen / YANBAND_ARALIK)} / 3 ölçüm → uyarı`
        : `${sureYaz(c.gecen)} / ${c.teyitAd} → ${c.tur === "kes" ? "kesme" : "uyarı"}`)),
    ].join("");
    // Yeniden başlatma izni: cep kartının ÇALIŞTIRMA satırı (yalıtım < 5 MΩ, PTC köprülü) ve kesme kilidi
    const sebepVar = o.k.some((c) => c.tur === "kes"); // kesme koşulu hâlâ eşiğin üstünde mi
    const engel = [kilit && sebepVar && "kesme kilitli, sebep sürüyor", o.r < 5 && "yalıtım 5 MΩ altında", ptc === "kopru" && "PTC köprülü"].filter(Boolean);
    $("m-baslatma").innerHTML = engel.length ? `<b class="kotu">Yeniden başlatma izni yok:</b> ${engel.join(" · ")}`
      : kilit ? "<b>Sebep giderildi.</b> Kilit elle açılır: yeniden çalıştırmak için Sıfırla'ya basın."
      : ptc === "kopuk" ? "Başlatma izni var · PTC ölçülemiyor, kablo onarılmalı"
      : o.r < 20 ? "Başlatma izni var · yalıtım düşük, bir sonraki ölçümde eğilime bakılır" : "Başlatma izni var";
    $("m-sifirla").hidden = !kilit;
    document.querySelectorAll("#m-senaryo [data-s]").forEach((b) => { if (b.dataset.s !== "normal") b.disabled = !!kilit; });
    return !kilit && t.bekleyen.length > 0; // kilitliyken motor durmuş, sayaçlar ilerlemez
  }

  function uygula(d) {
    for (const k of ALAN) if (k in d) $("m-" + k).value = d[k];
    if (d.ptc) ptcSec(d.ptc);
  }

  function senaryoAdim() {
    const { tam, sure, bas } = senaryo, t = Math.min(sure, (simSaat - bas) / HIZ);
    const i = Math.max(0, tam.findIndex(([tt]) => tt > t) - 1), [t0, a] = tam[i];
    const [t1, b] = tam[Math.min(tam.length - 1, i + 1)];
    const p = t1 > t0 ? Math.min(1, Math.max(0, (t - t0) / (t1 - t0))) : 1, ara = { ptc: a.ptc };
    for (const k of ALAN) ara[k] = a[k] + (b[k] - a[k]) * p;
    uygula(t >= sure ? tam.at(-1)[1] : ara);
    $("m-saat").textContent = `zaman 10 kat hızlı · +${Math.round(simSaat - bas)} s`;
    if (t >= sure) senaryo = null;
  }

  // Tek döngü: panel saatini ilerletir, senaryoyu oynatır; teyit bekleyen koşul ya da senaryo yoksa durur.
  function kare(simdi) {
    simSaat += Math.min(0.25, Math.max(0, (simdi - sonT) / 1000)) * HIZ; // kare zamanı olaydan önce olabilir: süre geri gitmesin; sekme arkadayken biriken süre tek seferde akmasın
    sonT = simdi;
    if (senaryo) senaryoAdim();
    const bekliyor = yaz();
    raf = bekliyor || senaryo ? requestAnimationFrame(kare) : 0;
  }
  const calis = () => { if (!raf) { sonT = performance.now(); raf = requestAnimationFrame(kare); } };

  function oynat(ad) {
    uygula(NORMAL);
    kilit = "";
    ilk.clear();
    document.querySelectorAll("#m-senaryo button").forEach((b) => b.classList.toggle("secili", b.dataset.s === ad && ad !== "normal"));
    $("m-saat").textContent = "zaman 10 kat hızlı";
    if (ad === "normal") { senaryo = null; yaz(); return; }
    const kare0 = SENARYO[ad], tam = [];
    // her kareyi bir öncekilerin üstüne yazarak tam durum listesine çevir
    kare0.reduce((onceki, [t, d]) => { const s = { ...onceki, ...d }; tam.push([t, s]); return s; }, { ...NORMAL });
    senaryo = { ad, tam, sure: kare0.at(-1)[0], bas: simSaat };
    calis();
  }

  const elle = () => { senaryo = null; $("m-saat").textContent = "zaman 10 kat hızlı"; document.querySelectorAll("#m-senaryo button.secili").forEach((b) => b.classList.remove("secili")); };
  motor.addEventListener("input", () => { elle(); yaz(); calis(); });
  $("m-ptc").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { elle(); ptcSec(b.dataset.p); yaz(); calis(); } });
  $("m-senaryo").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && !b.disabled) oynat(b.dataset.s); });
  $("m-sifirla").addEventListener("click", () => {
    if (kosullar().k.some((c) => c.tur === "kes")) { $("m-karar-aciklama").textContent = "Sebep sürüyor: kart sıfırlamayı kabul etmez. Önce sebebi giderin."; return; }
    kilit = "";
    ilk.clear();
    yaz();
    calis();
  });
  uygula(NORMAL);
  yaz();
}

// --- Stok: depo, tüketim tahmini ve otomatik sipariş. Örnek veriyle 30 gün; 1. gün pazartesi. ---
const depo = $("depo");
if (depo) {
  const GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
  const haftaSonu = (g) => g % 7 >= 5;
  const URUN = [
    // ad, birim, ortalama/gün, hafta sonu artışı %, dalgalanma %, tedarik (gün), emniyet (gün), sipariş kapsamı (gün)
    ["Döner eti", "kg", 18, 30, 20, 2, 1, 4], ["Lavaş", "adet", 140, 35, 15, 1, 1, 3], ["Ekmek", "adet", 90, 25, 15, 1, 1, 3],
    ["Patates", "kg", 25, 30, 20, 2, 1, 4], ["Ayran", "adet", 70, 40, 25, 3, 1, 5], ["Kola", "adet", 45, 40, 25, 4, 1, 6],
    ["Sos", "kg", 4, 20, 30, 5, 2, 7], ["Salata", "kg", 9, 25, 20, 1, 1, 3],
  ].map(([ad, birim, ort, hs, dalga, ted, emn, kap], i) => ({ ad, birim, ort, taban: ort, hs, dalga, ted, emn, kap, i }));
  let tohum = 11;
  const GURULTU = URUN.map(() => Array.from({ length: 30 }, () => 2 * ((tohum = (tohum * 16807) % 2147483647) / 2147483647) - 1));
  const ALFA = 0.3, UFUK = 7;
  const ort = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
  let secili = 0, sonuc = [];

  // Tahminci: hafta içi / hafta sonu katsayısı ve üstel düzeltilmiş seviye (α = 0,3).
  function tahminci(gecmis) {
    const hepsi = ort(gecmis), hs = gecmis.filter((_, g) => haftaSonu(g)), hi = gecmis.filter((_, g) => !haftaSonu(g));
    const kHS = hs.length && hepsi ? Math.max(0.05, ort(hs) / hepsi) : 1.15, kHI = hi.length && hepsi ? Math.max(0.05, ort(hi) / hepsi) : 0.95;
    const kat = (g) => (haftaSonu(g) ? kHS : kHI);
    let seviye = gecmis[0] / kat(0);
    gecmis.forEach((d, g) => { seviye = ALFA * (d / kat(g)) + (1 - ALFA) * seviye; });
    return { f: (g) => seviye * kat(g) };
  }

  // Tükenme: tahmini tüketimin kümülatif toplamı (tüketim hızının integrali) eldeki stoğa eşit olduğu an.
  function tukenme(t, g, stok, gelis = -1, miktar = 0) {
    let kalan = stok;
    for (let k = 1; k <= 60; k++) {
      if (g + k === gelis) kalan += miktar;
      const f = t.f(g + k);
      if (f >= kalan) return k - 1 + (f ? kalan / f : 0);
      kalan -= f;
    }
    return 60;
  }

  function simule(u) {
    const gun = [], gecmis = [], hata = []; // hata: dünkü tahmin ile bugün gerçekleşen (örneklem dışı)
    let stok = Math.round(u.ort * (u.ted + u.emn + u.kap)), gelis = -1, miktar = 0, dunku = null;
    for (let g = 0; g < 30; g++) {
      let geldi = 0, siparis = 0;
      if (g === gelis) { stok += miktar; geldi = miktar; gelis = -1; }
      const d = Math.max(0, Math.round(u.ort * (haftaSonu(g) ? 1 + u.hs / 100 : 1) * (1 + (u.dalga / 100) * GURULTU[u.i][g])));
      const tukendi = d > stok;
      stok = Math.max(0, stok - d);
      if (dunku) hata.push([d - dunku.f(g), d]);
      gecmis.push(d);
      const t = tahminci(gecmis), son = hata.slice(-7);
      t.sapma = hata.length ? Math.sqrt(ort(hata.map(([e]) => e * e))) : 0;
      t.hataYuzde = son.length ? Math.round(100 * ort(son.map(([e, x]) => Math.abs(e) / Math.max(x, 1)))) : null;
      dunku = t;
      // Stok, tedarik süresi + emniyet payı dolmadan bitecekse gün sonunda otomatik sipariş: geldiği günden başlayarak kapsam kadar.
      if (gelis < 0 && tukenme(t, g, stok) <= u.ted + u.emn) {
        miktar = Math.round(Array.from({ length: u.kap }, (_, k) => t.f(g + u.ted + k)).reduce((a, b) => a + b, 0));
        gelis = g + u.ted;
        siparis = miktar;
      }
      gun.push({ stok, d, geldi, siparis, tukendi, t, gelis, miktar: gelis < 0 ? 0 : miktar, T: tukenme(t, g, stok, gelis, gelis < 0 ? 0 : miktar), T0: tukenme(t, g, stok) });
    }
    return gun;
  }

  const gunAdi = (g) => GUN[((g % 7) + 7) % 7];
  const vakit = (k) => (k < 0.34 ? "sabah" : k < 0.67 ? "öğleden sonra" : "akşam");
  // T gün sonu referanslı: tam sayı T, o günün sonu (akşam); kesirli T, ertesi günün o kesrinde.
  const tukenmeYazi = (g, T) => { const k = T - Math.floor(T), tam = k < 1e-6;
    return T >= UFUK * 2 ? "iki haftadan sonra" : `≈ ${virgul(T)} gün sonra · ${gunAdi(g + (tam ? Math.round(T) : Math.ceil(T)))} ${tam ? "akşam" : vakit(k)}`; };

  function kart(u, k, g) {
    const d = sonuc[k][g];
    const durum = d.tukendi ? ["tukendi", "Tükendi"] : d.siparis ? ["siparis", `Sipariş: ${d.siparis} ${u.birim}`]
      : d.gelis >= 0 ? ["siparis", `Yolda · ${d.gelis - g} gün`] : d.geldi ? ["geldi", `Geldi: ${d.geldi} ${u.birim}`] : ["", "Yeterli"];
    const gun = sonuc[k], ust = Math.max(...gun.map((x) => x.stok), 1) * 1.1;
    const x = (i) => (i * 120) / 29, y = (v) => 31 - (v * 29) / ust;
    const iz = `<svg class="urun-iz" viewBox="0 0 120 32" preserveAspectRatio="none" aria-hidden="true">` +
      gun.map((s, i) => (haftaSonu(i) ? `<rect x="${x(i) - 2}" y="0" width="4" height="32" fill="#ffffff08"/>` : "")).join("") +
      `<polyline points="${gun.map((s, i) => `${x(i)},${y(s.stok)}`).join(" ")}" fill="none" stroke="#4a5361" stroke-width="1.5" vector-effect="non-scaling-stroke"/>` +
      `<polyline points="${gun.slice(0, g + 1).map((s, i) => `${x(i)},${y(s.stok)}`).join(" ")}" fill="none" stroke="var(--yazi)" stroke-width="2" vector-effect="non-scaling-stroke"/>` +
      // sıfır uzunluklu yuvarlak uçlu çizgi: esnetilen çizimde nokta yuvarlak kalır
      `<path d="M${x(g)} ${y(d.stok)}h0.01" stroke="var(--yazi)" stroke-width="6" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
    return `<button type="button" class="urun ${durum[0]}${k === secili ? " secili" : ""}" data-u="${k}" aria-pressed="${k === secili}">` +
      `<span class="urun-bas"><span>${u.ad}</span><span class="urun-durum">${durum[1]}</span></span>` +
      `<span class="urun-orta"><span class="urun-sayi">${d.stok}<small>${u.birim}</small></span>${iz}</span>` +
      `<span class="urun-alt">Tükenme ${d.T >= 14 ? "> 14 gün" : `≈ ${virgul(d.T)} gün`}</span></button>`;
  }

  function grafik(u, gun, g) {
    const kap = $("d-grafik"), W = Math.round(kap.clientWidth), dar = W < 560;
    const SOL = dar ? 30 : 44, SAG = 8, UST = 16, H1 = dar ? 110 : 130, ARA = 22, H2 = dar ? 44 : 54, H = UST + H1 + ARA + H2 + 20;
    const N = 30 + UFUK, x = (i) => SOL + ((i + 0.5) * (W - SOL - SAG)) / N, bw = Math.max(2, ((W - SOL - SAG) / N) * 0.62);
    const t = gun[g].t;
    // ileriye dönük stok: tahmini tüketim düşülür, yoldaki sipariş geldiği gün eklenir; bant nominal %80 (±1,28 σ √k, σ: geçmiş tahmin hatalarının RMSE değeri; hatalar bağımsız ve normal varsayılır)
    const ileri = [{ k: 0, v: gun[g].stok, s: 0 }];
    for (let k = 1; k <= UFUK && g + k < N; k++) {
      const onceki = ileri.at(-1).v + (g + k === gun[g].gelis ? gun[g].miktar : 0);
      ileri.push({ k, v: Math.max(0, onceki - t.f(g + k)), s: 1.28 * t.sapma * Math.sqrt(k) }); // simülasyondaki gibi stok eksiye düşmez
    }
    const ust1 = Math.max(...gun.map((s) => s.stok), ...ileri.map((p) => p.v + p.s), 1) * 1.08;
    const y1 = (v) => UST + H1 - (Math.max(0, v) * H1) / ust1;
    const tum = [...gun.map((s) => s.d), ...ileri.slice(1).map((p) => t.f(g + p.k))];
    const ust2 = Math.max(...tum, 1) * 1.1, y2 = (v) => UST + H1 + ARA + H2 - (v * H2) / ust2;
    let s = "";
    for (let i = 0; i < N; i++) if (haftaSonu(i)) s += `<rect x="${x(i) - (W - SOL - SAG) / N / 2}" y="${UST}" width="${(W - SOL - SAG) / N}" height="${H1 + ARA + H2}" fill="#ffffff07"/>`;
    for (const [v, y] of [[0, y1(0)], [Math.round(ust1 / 1.08), y1(ust1 / 1.08)]]) s += `<line x1="${SOL}" x2="${W - SAG}" y1="${y}" y2="${y}" stroke="#262d37"/><text x="${SOL - 4}" y="${y + 3}" class="eksen" text-anchor="end">${v}</text>`;
    s += `<text x="${SOL}" y="${UST - 4}" class="eksen">STOK (${u.birim})</text><text x="${SOL}" y="${UST + H1 + ARA - 6}" class="eksen">GÜNLÜK TÜKETİM · hafta sonu açık renkli</text>`;
    // geçmiş stok, sipariş ve teslimat işaretleri
    s += `<polyline points="${gun.slice(0, g + 1).map((d, i) => `${x(i)},${y1(d.stok)}`).join(" ")}" fill="none" stroke="var(--yazi)" stroke-width="2"/>`;
    gun.slice(0, g + 1).forEach((d, i) => {
      if (d.siparis) s += `<path d="M${x(i) - 5} ${y1(d.stok) - 12}h10l-5 7z" fill="var(--altin)"><title>${i + 1}. gün sipariş: ${d.siparis} ${u.birim}</title></path>`;
      if (d.geldi) s += `<path d="M${x(i) - 5} ${y1(d.stok) + 12}h10l-5 -7z" fill="var(--mavi)"><title>${i + 1}. gün teslim: ${d.geldi} ${u.birim}</title></path>`;
      if (d.tukendi) s += `<rect x="${x(i) - bw / 2}" y="${y1(0) - 3}" width="${bw}" height="3" fill="var(--kirmizi)"/>`;
    });
    // tahmin bandı ve çizgisi
    if (ileri.length > 1) {
      const ust = ileri.map((p) => `${x(g + p.k)},${y1(p.v + p.s)}`), alt = ileri.map((p) => `${x(g + p.k)},${y1(p.v - p.s)}`).reverse();
      s += `<polygon points="${[...ust, ...alt].join(" ")}" fill="var(--altin)" opacity=".12"/>`;
      s += `<polyline points="${ileri.map((p) => `${x(g + p.k)},${y1(p.v)}`).join(" ")}" fill="none" stroke="var(--altin)" stroke-width="2" stroke-dasharray="5 4"/>`;
      const T = gun[g].T;
      if (T < UFUK) {
        const xt = x(g) + (T * (W - SOL - SAG)) / N;
        s += `<circle cx="${xt}" cy="${y1(0)}" r="5" fill="var(--kirmizi)"/><text x="${xt}" y="${y1(0) - 9}" class="eksen kirmizi" text-anchor="middle">tükenme</text>`;
      }
    }
    // tüketim çubukları: geçmiş dolu, tahmin boş
    gun.slice(0, g + 1).forEach((d, i) => { s += `<rect x="${x(i) - bw / 2}" y="${y2(d.d)}" width="${bw}" height="${y2(0) - y2(d.d)}" fill="${haftaSonu(i) ? "#c9cdd3" : "#6b7480"}"/>`; });
    ileri.slice(1).forEach((p) => { const v = t.f(g + p.k); s += `<rect x="${x(g + p.k) - bw / 2}" y="${y2(v)}" width="${bw}" height="${y2(0) - y2(v)}" fill="none" stroke="var(--altin)" stroke-width="1.2"/>`; });
    // bugün çizgisi ve gün ekseni
    s += `<line x1="${x(g)}" x2="${x(g)}" y1="${UST}" y2="${y2(0)}" stroke="var(--yazi)" stroke-dasharray="2 3" opacity=".7"/><text x="${x(g) + 4}" y="${UST + 10}" class="eksen">bugün</text>`;
    for (let i = 0; i < N; i += dar ? 7 : 5) s += `<text x="${x(i)}" y="${H - 6}" class="eksen" text-anchor="middle">${i + 1}</text>`;
    kap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${u.ad}: 30 günlük stok ve tüketim, sonraki ${UFUK} günün tahmini">${s}</svg>`;
  }

  function ayrinti(g) {
    const u = URUN[secili], gun = sonuc[secili], d = gun[g];
    $("d-ad").textContent = `${u.ad} · ${d.stok} ${u.birim}`;
    $("d-tahmin").textContent = `Tahmini tükenme ${tukenmeYazi(g, d.T)}` +
      (d.gelis >= 0 && d.T0 < d.T - 0.05 ? ` (yoldaki siparişle; eldeki stokla ≈ ${virgul(d.T0)} gün)` : "");
    $("d-oneri").innerHTML = d.siparis ? `<b>Bugün otomatik sipariş verildi:</b> ${d.siparis} ${u.birim}, ${u.ted} gün sonra gelir`
      : d.gelis >= 0 ? `<b>Sipariş yolda:</b> ${d.miktar} ${u.birim}, ${d.gelis - g} gün sonra`
      : d.T - u.ted - u.emn < 1 ? `<b>Sipariş zamanı geldi:</b> tahmin tutarsa yarın otomatik sipariş verilir`
      : `<b>Sipariş gerekmez.</b> Son sipariş günü ${gunAdi(g + Math.floor(d.T - u.ted - u.emn))}`;
    $("d-ort").max = Math.max(40, u.taban * 2); // sınır başlangıç değerinden: anlık değerden alınırsa kaydırdıkça büyüyüp kaçıyor
    for (const k of ["ort", "hs", "dalga", "ted", "emn", "kap"]) {
      $("d-" + k).value = u[k];
      $(`d-${k}-y`).value = u[k];
    }
    document.querySelectorAll(".d-birim").forEach((e) => { e.textContent = u.birim; });
    $("d-yontem").textContent = `Tahmin: hafta içi / hafta sonu katsayısı + üstel düzeltme (α 0,3)` +
      (d.t.hataYuzde != null ? `, son 7 günde ortalama hata %${d.t.hataYuzde}` : "") +
      ` · Tükenme: tahmini tüketimin integrali stoğa eşit olduğunda.`;
    grafik(u, gun, g);
  }

  function ciz() {
    const g = Number($("depo-gun").value) - 1;
    $("depo-gun-y").textContent = `${g + 1}. gün · ${gunAdi(g)}${haftaSonu(g) ? " · hafta sonu" : ""}`;
    const bugun = sonuc.filter((s) => s[g].siparis).length, yolda = sonuc.filter((s) => s[g].gelis >= 0).length;
    const toplam = sonuc.reduce((a, s) => a + s.slice(0, g + 1).filter((d) => d.tukendi).length, 0);
    const yakin = sonuc.reduce((en, s, k) => (s[g].T < sonuc[en][g].T ? k : en), 0);
    $("depo-ozet").innerHTML = `<span>Bugün <b>${bugun}</b> otomatik sipariş</span><span><b>${yolda}</b> sipariş yolda</span>` +
      `<span class="uyar">En yakın tükenme (yoldakiler dahil): <b>${URUN[yakin].ad} ≈ ${virgul(sonuc[yakin][g].T)} gün</b></span><span>Şu ana kadar talebi karşılanamayan ürün-gün: <b>${toplam}</b></span>`;
    const odak = document.activeElement?.closest?.("#depo-kartlar [data-u]")?.dataset.u; // yeniden çizimde odak kartta kalsın
    $("depo-kartlar").innerHTML = URUN.map((u, k) => kart(u, k, g)).join("");
    if (odak != null) $("depo-kartlar").querySelector(`[data-u="${odak}"]`).focus();
    ayrinti(g);
  }

  let zamanlayici = null;
  const durdur = () => { clearInterval(zamanlayici); zamanlayici = null; $("depo-oynat").textContent = "▶ Oynat"; };
  const oynat = () => {
    if (zamanlayici) return durdur();
    if (Number($("depo-gun").value) >= 30) { $("depo-gun").value = 1; ciz(); }
    $("depo-oynat").textContent = "⏸ Durdur";
    zamanlayici = setInterval(() => {
      const s = $("depo-gun");
      if (Number(s.value) >= 30) return durdur();
      s.value = Number(s.value) + 1;
      ciz();
    }, 700);
  };
  $("depo-oynat").addEventListener("click", oynat);
  $("depo-gun").addEventListener("input", () => { durdur(); ciz(); });
  $("depo-kartlar").addEventListener("click", (e) => { const b = e.target.closest("[data-u]"); if (b) { secili = Number(b.dataset.u); ciz(); } });
  depo.querySelector(".ayrinti-ayar").addEventListener("input", (e) => {
    const u = URUN[secili], alan = e.target.id.slice(2);
    u[alan] = Number(e.target.value);
    sonuc[secili] = simule(u);
    ciz();
  });
  let sonW = 0;
  new ResizeObserver(() => { const w = $("d-grafik").clientWidth; if (w !== sonW) { sonW = w; ciz(); } }).observe($("d-grafik"));
  sonuc = URUN.map(simule);
  $("depo-gun").value = 9;
  ciz();
  if (!azHareket) {
    // Görününce bir kez baştan oynar; ziyaretçi daha önce bir şeye dokunduysa seçimine karışmaz.
    let dokunuldu = false;
    for (const olay of ["input", "click"]) depo.addEventListener(olay, () => { dokunuldu = true; }, true);
    const gozcu = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      gozcu.disconnect();
      if (!dokunuldu) { $("depo-gun").value = 1; ciz(); oynat(); }
    }, { threshold: 0.3 });
    gozcu.observe(depo);
  }
}

// --- Akıllı ev: üç kişilik evin bir günü. Ev planı ve lojik analizör kaydı aynı saate bağlı. ---
const evKap = $("ev-kayit");
if (evKap) {
  const T0 = 6, T1 = 24, DARBE = 0.1;
  // grup, ad, kısa ad, renk, tür, veri
  const KANAL = [
    ["giris", "KAPI", "KAPI", "#8fb8e8", "darbe", [7.25, 7.67, 9.15, 17.73, 18.65, 19.48]],
    ["giris", "İÇERİDE", "İÇ", "#ece8df", "yol", [[6, 7.25, "3"], [7.25, 7.67, "2"], [7.67, 9.15, "1"], [9.15, 17.73, "0"], [17.73, 18.65, "1"], [18.65, 19.48, "2"], [19.48, 24, "3"]]],
    ["giris", "KİMLİK", "KİM", "#86c9a3", "etiket", [[17.73, "2"], [18.65, "1"], [19.48, "3"]]],
    ["isik", "ODA 1", "O1", "#d9ad4f", "seviye", [[6.5, 7.25], [23, 23.5]]],
    ["isik", "ODA 2", "O2", "#d9ad4f", "seviye", [[6.6, 7.67], [20, 23.6]]],
    ["isik", "ODA 3", "O3", "#d9ad4f", "seviye", [[8.5, 9.15], [23, 23.4]]],
    ["isik", "SALON", "SLN", "#f0c870", "seviye", [[6.95, 7.7], [8.6, 9.15], [17.75, 23.1]]],
    ["isik", "MUTFAK", "MTF", "#f0c870", "seviye", [[6.95, 7.7], [8.5, 9.15], [19, 20.1]]],
    ["cihaz", "KAHVE", "KHV", "#e0915a", "seviye", [[17.45, 17.8]]],
    ["cihaz", "SICAK SU", "SU", "#6fc3d6", "seviye", [[6.4, 6.75]]],
    ["cihaz", "HAVALANDIRMA", "HAV", "#b59ae0", "seviye", [[7.0, 7.4], [10, 10.75]]],
    ["ortam", "HAREKET", "HRK", "#ef8a78", "darbe", [6.75, 6.95, 7.3, 7.67, 8.5, 9.15, 17.73, 18.65, 19, 19.48, 20, 20.3, 21.1, 22.4]],
    ["ortam", "SICAKLIK", "°C", "#ef8a78", "analog", [[6, 21.4], [7, 22.3], [7.7, 22.6], [9.2, 22], [12, 20.6], [16, 19.8], [17.8, 20.4], [19, 22.2], [21, 22.8], [24, 22.1]], 18, 24],
    ["ortam", "NEM", "NEM", "#8fb8e8", "analog", [[6, 46], [6.8, 47], [7, 71], [7.4, 52], [7.8, 48], [12, 44], [17, 43], [19.2, 49], [19.8, 56], [20.5, 50], [24, 47]], 35, 80],
  ];
  // kişi: renk ve [başlangıç, bitiş, yer]
  const KISI = [
    ["#8fb8e8", [[6, 6.95, "oda1"], [6.95, 7.25, "mutfak"], [7.25, 18.65, "dis"], [18.65, 19, "salon"], [19, 20, "mutfak"], [20, 23, "salon"], [23, 24, "oda1"]]],
    ["#86c9a3", [[6, 6.75, "oda2"], [6.75, 7, "banyo"], [7, 7.3, "oda2"], [7.3, 7.67, "mutfak"], [7.67, 17.73, "dis"], [17.73, 19, "salon"], [19, 20, "mutfak"], [20, 24, "oda2"]]],
    ["#e0915a", [[6, 8.5, "oda3"], [8.5, 9.15, "mutfak"], [9.15, 19.48, "dis"], [19.48, 20, "mutfak"], [20, 23, "salon"], [23, 24, "oda3"]]],
  ];
  const OLAY = [
    [6.4, "Sıcak su, 2. kişinin duşundan önce ısınmaya başladı"],
    [7.0, "Duştan sonra nem yükseldi, banyo havalandırması açıldı"],
    [7.25, "1. kişi çıktı, odasının ışığı kapandı"],
    [9.15, "Ev boşaldı, ortak ışıklar kapandı"],
    [10.0, "Ev boşken 3. kişinin odası havalandırılıyor"],
    [17.45, "2. kişi eve yaklaşıyor, kahve hazırlanmaya başladı"],
    [18.65, "1. kişi geldi, telefonuyla kimliği doğrulandı"],
  ];
  const HARF = "ABCDEFG";
  const sinir = (t) => Math.min(t, T1 - 1e-6);
  const araliklar = (k) => (k[4] === "darbe" ? k[5].map((t) => [t, t + DARBE]) : k[4] === "etiket" ? k[5].map(([t, e]) => [t, t + 0.15, e]) : k[5]);
  const etkin = (k, t) => araliklar(k).find((a) => sinir(t) >= a[0] && sinir(t) < a[1]);
  const analog = (k, t) => { const p = k[5], i = p.findIndex((q) => q[0] > t); if (i <= 0) return p[i < 0 ? p.length - 1 : 0][1]; const [a, b] = [p[i - 1], p[i]]; return a[1] + ((b[1] - a[1]) * (t - a[0])) / (b[0] - a[0]); };
  const yer = (kisi, t) => kisi[1].find((a) => sinir(t) >= a[0] && sinir(t) < a[1])[2];
  const saatYaz = (t) => { const d = Math.round(t * 60); return `${String(Math.floor(d / 60) % 24).padStart(2, "0")}:${String(d % 60).padStart(2, "0")}`; };

  // Ev planı (sabit 400x290): üstte üç oda, altta salon, mutfak, banyo; giriş salonun altında.
  const ODA = { oda1: [0, 0, 133, 120, "ODA 1"], oda2: [133, 0, 134, 120, "ODA 2"], oda3: [267, 0, 133, 120, "ODA 3"],
    salon: [0, 120, 190, 135, "SALON"], mutfak: [190, 120, 120, 135, "MUTFAK"], banyo: [310, 120, 90, 135, "BANYO"] };
  const ISIK = { oda1: 3, oda2: 4, oda3: 5, salon: 6, mutfak: 7 };
  let plan = "";
  for (const [ad, [x, y, w, hh, et]] of Object.entries(ODA)) {
    plan += `<rect id="oda-${ad}" class="oda" x="${x + 2}" y="${y + 2}" width="${w - 4}" height="${hh - 4}" rx="4"/>` +
      `<text class="oda-ad" x="${x + 10}" y="${y + 20}">${et}</text>`;
  }
  plan += `<rect id="ev-kapi" class="kapi" x="70" y="252" width="44" height="6" rx="2"/><text class="oda-ad" x="122" y="262">GİRİŞ</text>` +
    `<g id="ev-kahve" class="cihaz"><path d="M222 220h18v10a9 9 0 0 1-18 0zM240 223h4a4 4 0 0 1 0 8h-4"/></g>` +
    `<g id="ev-su" class="cihaz"><path d="M372 150a14 9 0 0 1 22 0zM383 140v-6"/><path d="M376 166l-2 6M383 166v7M390 166l2 6"/></g>` +
    `<g class="cihaz fan" id="ev-fan-banyo"><circle cx="355" cy="225" r="13"/><path d="M355 225c-2-8 2-12 7-12 0 6-3 10-7 12zM355 225c8-1 11 3 10 8-6 1-9-3-10-8zM355 225c-5 6-10 6-13 2 3-5 8-5 13-2z"/></g>` +
    `<g class="cihaz fan" id="ev-fan-oda3"><circle cx="370" cy="95" r="13"/><path d="M370 95c-2-8 2-12 7-12 0 6-3 10-7 12zM370 95c8-1 11 3 10 8-6 1-9-3-10-8zM370 95c-5 6-10 6-13 2 3-5 8-5 13-2z"/></g>` +
    `<circle id="ev-hareket" class="pir" cx="176" cy="136" r="5"/>` +
    `<text class="oda-ad" x="8" y="284">DIŞARIDA</text>` +
    KISI.map((k, i) => `<g id="kisi-${i}" class="kisi" style="transition:transform .5s"><circle r="11" fill="${k[0]}"/><text y="4" text-anchor="middle">${i + 1}</text></g>`).join("");
  $("ev-plan").innerHTML = `<svg viewBox="0 0 400 292" role="img" aria-describedby="ev-durum" aria-label="Evin planı: üç oda, salon, mutfak, banyo; ışıklar, cihazlar ve kişilerin yeri saate göre değişir">${plan}</svg>`;
  $("ev-olaylar").innerHTML = OLAY.map(([t, m], i) => `<button type="button" data-t="${t}" title="${h(m)}" aria-label="${HARF[i]}, ${saatYaz(t)}: ${h(m)}"><b>${HARF[i]}</b> ${saatYaz(t)}</button>`).join("");

  let g = null, saat = T0, dokunuldu = false, oynuyor = false, evRaf = 0;
  function ciz() {
    const W = Math.round(evKap.clientWidth), dar = W < 560;
    const LW = dar ? 40 : 104, X0 = LW + 8, X1 = W - 10, ust = dar ? 24 : 32, DY = dar ? 20 : 23, A = dar ? 6 : 7, fs = dar ? 9.5 : 11.5, ARA = dar ? 6 : 8;
    const satirY = [];
    let y = ust, onceki = KANAL[0][0];
    KANAL.forEach((k) => { if (k[0] !== onceki) { y += ARA; onceki = k[0]; } satirY.push(y); y += DY; });
    const alt = y - DY + A + 12, H = alt + 44;
    const x = (t) => X0 + ((t - T0) * (X1 - X0)) / (T1 - T0);
    let s = "";
    for (let t = T0; t <= T1; t += dar ? 6 : 3) {
      s += `<line x1="${x(t)}" x2="${x(t)}" y1="${ust - A - 4}" y2="${alt}" stroke="#262d37"/>` +
        `<text x="${x(t)}" y="${alt + 14}" font-size="${fs}" fill="#a1a9b3" text-anchor="${t === T1 ? "end" : "middle"}">${String(t % 24).padStart(2, "0")}:00</text>`;
    }
    KANAL.forEach((k, i) => {
      const yy = satirY[i], yu = yy - A, ya = yy + A;
      s += `<text x="4" y="${yy + 4}" font-size="${fs}" font-weight="600" fill="#ece8df">${k[dar ? 2 : 1]}</text>`;
      if (k[4] === "yol") {
        for (const [a, b, d] of k[5]) {
          const xa = x(a), xb = x(b), e = Math.min(5, (xb - xa) / 3);
          s += `<polygon points="${xa},${yy} ${xa + e},${yu} ${xb - e},${yu} ${xb},${yy} ${xb - e},${ya} ${xa + e},${ya}" fill="#1b2129" stroke="${k[3]}" stroke-width="1.3"/>`;
          if (xb - xa > fs * 1.6) s += `<text x="${(xa + xb) / 2}" y="${yy + 4}" font-size="${fs}" fill="${k[3]}" text-anchor="middle">${d}</text>`;
        }
        return;
      }
      if (k[4] === "analog") {
        const [, , , renk, , p, lo, hi] = k, yv = (v) => ya - ((v - lo) * (ya - yu)) / (hi - lo);
        s += `<polyline points="${p.map(([t, v]) => `${x(t)},${yv(v)}`).join(" ")}" fill="none" stroke="${renk}" stroke-width="1.6"/>`;
        return;
      }
      let d = `M${X0} ${ya}`;
      for (const [a, b] of araliklar(k)) d += ` H${x(a)} V${yu} H${x(b)} V${ya}`;
      s += `<path d="${d} H${X1}" fill="none" stroke="${k[3]}" stroke-width="1.8" stroke-linejoin="round"/>`;
      if (k[4] === "etiket") for (const [t, e] of k[5]) s += `<text x="${x(t) + 6}" y="${yu + 1}" font-size="${fs}" fill="${k[3]}">${e}</text>`;
    });
    OLAY.forEach(([t], j) => {
      s += `<line x1="${x(t)}" x2="${x(t)}" y1="${ust - A - 10}" y2="${alt}" stroke="#d9ad4f" stroke-dasharray="3 4" opacity=".8"/>` +
        `<text x="${x(t)}" y="${ust - A - 13}" font-size="${fs}" fill="#d9ad4f" text-anchor="middle">${HARF[j]}</text>`;
    });
    s += `<g id="ev-imlec"><line y1="${ust - A - 6}" y2="${alt}" stroke="#ece8df" stroke-width="1.5"/>` +
      `<rect y="${alt + 20}" width="48" height="20" rx="4" fill="#ece8df"/><text y="${alt + 34}" font-size="12" font-weight="600" fill="#0f1217" text-anchor="middle"></text></g>`;
    evKap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="Lojik analizör görünümünde günün kaydı: giriş-çıkış, ışıklar, cihazlar ve ortam kanalları">${s}</svg>`;
    g = { x, X0, X1, W };
    yaz(saat);
  }

  function yaz(t) {
    saat = t;
    const metin = saatYaz(t);
    $("ev-saat").textContent = metin;
    $("ev-saat-girdi").value = Math.round(t * 60);
    $("ev-saat-girdi").setAttribute("aria-valuetext", t >= T1 ? "24:00, gün sonu" : metin);
    const AD = { 0: "kapı", 11: "hareket algısı", 3: "oda 1 ışığı", 4: "oda 2 ışığı", 5: "oda 3 ışığı", 6: "salon ışığı", 7: "mutfak ışığı", 8: "kahve makinesi", 9: "sıcak su", 10: "havalandırma" };
    const acik = Object.keys(AD).filter((i) => etkin(KANAL[i], t)).map((i) => AD[i]);
    $("ev-durum").textContent = `Saat ${metin}. Açık: ${acik.length ? acik.join(", ") : "hiçbiri"}.`;
    for (const [ad, i] of Object.entries(ISIK)) $("oda-" + ad).classList.toggle("yanik", !!etkin(KANAL[i], t));
    $("oda-banyo").classList.toggle("sicak", !!etkin(KANAL[9], t));
    $("ev-kahve").classList.toggle("acik", !!etkin(KANAL[8], t));
    $("ev-su").classList.toggle("acik", !!etkin(KANAL[9], t));
    const hav = etkin(KANAL[10], t);
    $("ev-fan-banyo").classList.toggle("acik", !!hav && t < 9);
    $("ev-fan-oda3").classList.toggle("acik", !!hav && t >= 9);
    $("ev-kapi").classList.toggle("acik", !!etkin(KANAL[0], t));
    $("ev-hareket").classList.toggle("acik", !!etkin(KANAL[11], t));
    // kişileri bulundukları odaya yerleştir (aynı odada yan yana)
    const yerler = KISI.map((k) => yer(k, t)), sayac = {};
    KISI.forEach((k, i) => {
      const y = yerler[i], n = (sayac[y] = (sayac[y] || 0) + 1) - 1, toplam = yerler.filter((z) => z === y).length;
      const [ox, oy, ow, oh] = y === "dis" ? [80, 262, 120, 28] : ODA[y];
      const px = y === "dis" ? ox + 18 + n * 28 : ox + ow / 2 + (n - (toplam - 1) / 2) * 26, py = y === "dis" ? 277 : oy + oh / 2 + 10;
      $("kisi-" + i).setAttribute("transform", `translate(${px} ${py})`);
    });
    const kisiYaz = (y) => ({ dis: "dışarıda", banyo: "banyoda", mutfak: "mutfakta", salon: "salonda" }[y] || "odasında");
    $("ev-kisiler").innerHTML = KISI.map((k, i) => `<li><span class="nokta-k" style="background:${k[0]}"></span>${i + 1}. kişi ${kisiYaz(yer(k, t))}</li>`).join("");
    $("ev-ortam").textContent = `${virgul(analog(KANAL[12], t))} °C · nem %${Math.round(analog(KANAL[13], t))}`;
    const yakin = OLAY.findLastIndex(([ti]) => t >= ti - 1e-6 && t - ti < 0.25);
    $("ev-not").textContent = yakin < 0 ? "" : `${HARF[yakin]} · ${OLAY[yakin][1]}`;
    document.querySelectorAll("#ev-olaylar button").forEach((b, i) => b.classList.toggle("secili", i === yakin));
    if (!g) return;
    const xi = g.x(t), im = $("ev-imlec");
    im.querySelector("line").setAttribute("x1", xi);
    im.querySelector("line").setAttribute("x2", xi);
    const bx = Math.min(Math.max(xi - 24, 0), g.W - 48);
    im.querySelector("rect").setAttribute("x", bx);
    im.querySelector("text").setAttribute("x", bx + 24);
    im.querySelector("text").textContent = metin;
  }

  const surukle = (e) => {
    const r = evKap.firstChild.getBoundingClientRect(), xs = ((e.clientX - r.left) * g.W) / r.width;
    yaz(Math.min(T1, Math.max(T0, T0 + ((xs - g.X0) * (T1 - T0)) / (g.X1 - g.X0))));
  };
  // Oynat / durdur: kaldığı saatten gün sonuna 16 saniyelik ölçekte ilerler; ziyaretçi elle değiştirince durur.
  const evDurdur = () => { oynuyor = false; cancelAnimationFrame(evRaf); $("ev-oynat").textContent = "▶ Oynat"; };
  const evOynat = () => {
    if (oynuyor) return evDurdur();
    if (saat >= T1 - 0.01) yaz(T0);
    oynuyor = true;
    $("ev-oynat").textContent = "⏸ Durdur";
    const bas = performance.now(), t0 = saat, sure = (16000 * (T1 - t0)) / (T1 - T0);
    const adim = (simdi) => {
      if (!oynuyor) return;
      const p = Math.min(1, Math.max(0, (simdi - bas) / sure)); // kare zamanı tıklamadan önce olabilir
      yaz(t0 + p * (T1 - t0));
      if (p < 1) evRaf = requestAnimationFrame(adim); else evDurdur();
    };
    evRaf = requestAnimationFrame(adim);
  };
  const elle = () => { dokunuldu = true; evDurdur(); };
  $("ev-oynat").addEventListener("click", () => { dokunuldu = true; evOynat(); });
  evKap.addEventListener("pointerdown", (e) => { elle(); evKap.setPointerCapture(e.pointerId); surukle(e); });
  evKap.addEventListener("pointermove", (e) => { if (evKap.hasPointerCapture(e.pointerId)) surukle(e); });
  $("ev-saat-girdi").addEventListener("input", (e) => { elle(); yaz(e.target.value / 60); });
  $("ev-olaylar").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { elle(); yaz(Number(b.dataset.t)); } });
  new ResizeObserver(() => { if (Math.round(evKap.clientWidth) !== g?.W) ciz(); }).observe(evKap);
  ciz();

  // Görününce bir kez baştan sona oynar; ziyaretçi önce bir şeye dokunduysa oynamaz.
  if (!azHareket) {
    const gozcu = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      gozcu.disconnect();
      if (!dokunuldu) evOynat();
    }, { threshold: 0.35 });
    gozcu.observe(evKap);
  }
}
