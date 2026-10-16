// Statik veri dosyalarını okuyan ortak işlevler (arama sayfası ve BOM raporu kullanır).
const VERI = "veri/";
const onbellek = new Map();

export const h = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const anahtar = (s) => s.toUpperCase().replace(/[^A-Z0-9]/g, "");
export const sayi = (n) => (n ?? 0).toLocaleString("tr-TR");
export const dolar = (n) => (n == null ? "-" : "$" + (n < 0.01 ? n.toPrecision(3) : n.toFixed(n < 1 ? 4 : 2)));

export async function gz(yol) {
  if (onbellek.has(yol)) return onbellek.get(yol);
  const is = (async () => {
    const y = await fetch(VERI + yol);
    if (!y.ok) throw Object.assign(new Error(`${yol}: ${y.status}`), { durum: y.status });
    const ham = new Uint8Array(await y.arrayBuffer());
    // Sunucu dosyayı zaten açmış olabilir (Content-Encoding): gzip imzası (1f 8b) varsa biz açarız.
    if (ham[0] === 0x1f && ham[1] === 0x8b) {
      const akis = new Blob([ham]).stream().pipeThrough(new DecompressionStream("gzip"));
      return JSON.parse(await new Response(akis).text());
    }
    return JSON.parse(new TextDecoder().decode(ham));
  })();
  onbellek.set(yol, is);
  is.catch(() => onbellek.delete(yol));
  return is;
}

export let meta, dizin;
export async function hazirla() {
  [meta, dizin] = await Promise.all([gz("meta.json"), gz("ara/_dizin.json")]);
  return meta;
}

const ALT_SINIR = 8;
function parcalar(k) {
  // Dizindeki her ad bir dosya: "LM3" LM3 ile başlayan anahtarları, "_" ile biten "LM_" yalnız "LM" anahtarını
  // ("__" boş anahtarı) taşır. Sorgu "_"suz bir dosyanın içine düşüyorsa o yeter; yoksa sorgu bölünmüş bir önekte
  // bitiyor ("LM" -> LM_, LM0 ... LMZ): alt dosyalar okunur, sınırı aşarsa sonuç eksik işaretlenir.
  const ev = dizin.find((o) => !o.includes("_") && k.startsWith(o));
  if (ev) return { liste: [ev], eksik: false };
  const alt = dizin.filter((o) => o.startsWith(k)).sort((a, b) => (b === k + "_") - (a === k + "_"));
  return { liste: alt.slice(0, ALT_SINIR), eksik: alt.length > ALT_SINIR };
}

/** Parça kaydı; katalogda yoksa null. Dosya okunamazsa hata fırlatır ("yok" ile "okunamadı" karışmasın). */
export async function parca(lcsc) {
  const no = parseInt(lcsc.slice(1), 10);
  const kova = await gz(`p/${Math.floor(no / meta.kova)}.json`).catch((e) => {
    if (e.durum === 404) return []; // o aralıkta hiç parça yok
    throw e;
  });
  return kova.find((r) => r.c === lcsc) || null;
}

/** Arama satırları: [mpn, lcsc, üretici, kılıf, stok]. Birebir eşleşme ile benzerler ayrı döner;
 * eksik: kısa sorguda yalnız bir kısım dosya okundu. Dosya okunamazsa hata fırlatır. */
export async function bul(q) {
  q = q.trim();
  const k = anahtar(q);
  if (k.length < 2) return { birebir: [], yakin: [], eksik: false };
  const { liste, eksik } = parcalar(k);
  const satirlar = (await Promise.all(liste.map((o) => gz(`ara/${o}.json`)))).flat();
  const Q = q.toUpperCase();
  const birebir = satirlar.filter((s) => s[0].toUpperCase() === Q).sort((a, b) => b[4] - a[4]);
  const yakin = satirlar.filter((s) => s[0].toUpperCase() !== Q && anahtar(s[0]).startsWith(k))
    .sort((a, b) => a[0].length - b[0].length || b[4] - a[4]).slice(0, 15);
  return { birebir, yakin, eksik };
}
