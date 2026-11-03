import { el, fetchJson } from './util';

// Old pictures of a labelled place (scripts/photos.py: the city archive's copyright-free photos, prints and drawings),
// in a panel on the right when its label is clicked: the one nearest the year slider's year first. Thumbnails come
// from the archive's image server; each links to its record there.
interface Pic { year: number; title: string; kind: string; by: string | null; thumb: string; link: string }
interface Place { name: string; x: number; y: number; items: Pic[] }

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);
const KIND: Record<string, string> = { foto: 'photo', prent: 'print', tekening: 'drawing', prentbriefkaart: 'postcard', aquarel: 'watercolour', schilderij: 'painting' };

export class Photos {
  private readonly el = el('aside', 'photos');
  private readonly places = new Map<string, Place>();
  private open: string | null = null;

  constructor() {
    this.el.hidden = true;
    this.el.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('.close')) this.hide(); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape') this.hide(); });
    fetchJson<{ places: Place[] }>('data/photos.json').then((d) => d.places.forEach((p) => this.places.set(p.name, p))).catch(() => {});
  }

  has(name: string) { return this.places.has(name); }

  show(name: string, year: number) {
    const p = this.places.get(name);
    if (!p) { this.hide(); return; }
    this.open = name;
    const items = [...p.items].sort((a, b) => Math.abs(a.year - year) - Math.abs(b.year - year) || a.year - b.year);
    this.el.innerHTML = `<header><b>${esc(name)}</b> <span>then</span><button class="close" aria-label="Close">✕</button></header>
      <ol>${items.map((i) => `<li><a href="${esc(i.link)}" target="_blank" rel="noopener">
        <img src="${esc(i.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        <span class="y">${i.year}</span> <span class="k">${KIND[i.kind] ?? esc(i.kind)}${i.by ? ` · ${esc(i.by)}` : ''}</span>
        <small>${esc(i.title)}</small></a></li>`).join('')}</ol>
      <footer>Stadsarchief Amsterdam, Beeldbank · copyright-free records</footer>`;
    this.el.hidden = false;
  }

  // the year slider moved: the panel re-sorts round the new year
  setYear(year: number) { if (this.open) this.show(this.open, year); }

  hide() { this.el.hidden = true; this.open = null; }
}
