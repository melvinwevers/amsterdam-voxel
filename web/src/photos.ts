import type { Facts } from './types';
import { el, fetchJson } from './util';

// A labelled place's panel, on the right when its label is clicked or it is chosen in search: what it is, then its
// old pictures (scripts/photos.py, photos_commons.py: the city archive's copyright-free photos, prints and drawings,
// Wikimedia Commons' free ones), the one nearest the year slider's year first, each with its description and credit.
// No links out of the viewer: the images are shown from the archive's and Commons' image servers.
interface Pic { year: number; title: string; kind: string; by: string | null; thumb: string; link: string; license?: string }
interface Place { name: string; x: number; y: number; items: Pic[] }

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);
const KIND: Record<string, string> = { foto: 'photo', prent: 'print', tekening: 'drawing', prentbriefkaart: 'postcard', aquarel: 'watercolour', schilderij: 'painting', commons: 'Wikimedia Commons' };

export class Photos {
  private readonly el = el('aside', 'photos');
  private readonly places = new Map<string, Place>();
  private open: Facts | null = null;

  constructor() {
    this.el.hidden = true;
    this.el.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('.close')) this.hide(); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape') this.hide(); });
    fetchJson<{ places: Place[] }>('data/photos.json').then((d) => d.places.forEach((p) => this.places.set(p.name, p))).catch(() => {});
  }

  has(name: string) { return this.places.has(name); }

  show(f: Facts, year: number) {
    const p = this.places.get(f.name);
    this.open = f;
    const what = [f.en, f.kind, f.year && `${f.year}`, f.rebuilt && `rebuilt ${f.rebuilt}`, f.by, f.height && `${f.height} m`]
      .filter(Boolean).map((s) => esc(String(s))).join(' · ');
    const items = p ? [...p.items].sort((a, b) => Math.abs(a.year - year) - Math.abs(b.year - year) || a.year - b.year) : [];
    this.el.innerHTML = `<header><b>${esc(f.name)}</b><button class="close" aria-label="Close">✕</button></header>
      ${what ? `<p class="what">${what}</p>` : ''}
      ${items.length ? `<h4>Then</h4><ol>${items.map((i) => `<li><figure>
        <img src="${esc(i.thumb)}" alt="${esc(i.title)}" loading="lazy" referrerpolicy="no-referrer">
        <figcaption><span class="y">${i.year}</span> <span class="k">${KIND[i.kind] ?? esc(i.kind)}${i.by ? ` · ${esc(i.by)}` : ''}${i.license ? ` · ${esc(i.license)}` : ''}</span>
        <small>${esc(i.title)}</small></figcaption></figure></li>`).join('')}</ol>
      <footer>Stadsarchief Amsterdam, Beeldbank (copyright-free records) · Wikimedia Commons (licence per picture)</footer>` : ''}`;
    this.el.hidden = false;
  }

  // the year slider moved: the panel re-sorts round the new year
  setYear(year: number) { if (this.open) this.show(this.open, year); }

  hide() { this.el.hidden = true; this.open = null; }
}
