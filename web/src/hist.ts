import * as THREE from 'three';
import type { MeshReply, MeshRequest } from './mesher.worker';
import { fetchGzip } from './util';

// The city of 1832 where it has gone since (scripts/hist1832.py): level-1 tiles holding only those buildings, meshed
// with their building ids numbered after today's (nb + k), so city.ts's per-building flags show each one in the years
// it stood. Loaded the first time the year slider goes into the past.
export interface HistIndex { N: number; tiles: [number, number][]; buildings: [number, number, number, string][] }

export async function loadHist(index: HistIndex, nb: number, W: number, D: number, material: THREE.Material,
  depth: THREE.Material, parent: THREE.Object3D) {
  const ids = new Uint16Array(await fetchGzip('data/hist/ids.bin'));
  const { N } = index;
  const worker = new Worker(new URL('./mesher.worker.ts', import.meta.url), { type: 'module' });
  const waiting = new Map<string, (m: MeshReply) => void>();
  worker.onmessage = (e: MessageEvent<MeshReply>) => waiting.get(e.data.key)?.(e.data);
  const meshes: THREE.Mesh[] = [];
  for (const [tx, ty] of index.tiles) {
    const bld = new Uint16Array(N * N);
    for (let y = 0; y < N; y++) {
      const r = ty * N + y;
      if (r >= D) break;
      for (let x = 0; x < N; x++) {
        const c = tx * N + x;
        if (c >= W) break;
        const k = ids[r * W + c];
        if (k) bld[y * N + x] = nb + k;
      }
    }
    const key = `h${tx}_${ty}`;
    const req: MeshRequest = { key, url: new URL(`data/hist/${tx}_${ty}.bin`, location.href).href, N, s: 1, x0: tx * N, y0: ty * N,
      keep: false, dataOnly: false, bld };
    const m = await new Promise<MeshReply>((res) => { waiting.set(key, res); worker.postMessage(req, [bld.buffer]); });
    if (m.type !== 'node') { console.warn('hist', key, m.error); continue; }
    if (!m.quads) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3));
    geo.setAttribute('vattr', new THREE.BufferAttribute(m.attr, 4));
    geo.setAttribute('vpal', new THREE.BufferAttribute(m.pal, 1));
    if (m.bld) geo.setAttribute('vbld', new THREE.BufferAttribute(m.bld, 1));
    const idx = new Uint32Array(m.quads * 6);
    for (let q = 0, b = 0; q < m.quads; q++, b += 4) idx.set([b, b + 1, b + 2, b, b + 2, b + 3], q * 6);
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.computeBoundingBox(); geo.computeBoundingSphere();
    const mesh = new THREE.Mesh(geo, material);
    mesh.customDepthMaterial = depth;
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.matrixAutoUpdate = false;
    parent.add(mesh);
    meshes.push(mesh);
  }
  worker.terminate();
  return meshes;
}
