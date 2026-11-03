import * as THREE from 'three';
import type { MeshReply, MeshRequest } from './mesher.worker';
import { fetchJson } from './util';
import { makeVoxelMaterial, type VoxelUniforms } from './voxelMaterial';

// Landmarks at 0.5 m (scripts/insets.py): each a small tile of its own, meshed at unit scale (the mesher keeps
// vertex positions in whole cells) and placed by its mesh matrix at half scale. city.ts hides the 1 m buildings they
// replace and shows them only in the years they stand.
export interface Inset { key: string; x0: number; y0: number; N: number; r: number; bld: number[]; year: number; file: string }

export async function loadInsets(uniforms: VoxelUniforms, scene: THREE.Object3D) {
  const { insets } = await fetchJson<{ insets: Inset[] }>('data/insets/index.json');
  // their own material: not the building one, whose per-building flags would hide them with the 1 m versions
  const { uStage: _s, uBldOn: _b, uYearOn: _y, uYear: _yy, ...plain } = uniforms as VoxelUniforms & Record<string, THREE.IUniform>;
  const material = makeVoxelMaterial(plain as VoxelUniforms);
  const worker = new Worker(new URL('./mesher.worker.ts', import.meta.url), { type: 'module' });
  const waiting = new Map<string, (m: MeshReply) => void>();
  worker.onmessage = (e: MessageEvent<MeshReply>) => waiting.get(e.data.key)?.(e.data);
  const out: (Inset & { mesh: THREE.Mesh })[] = [];
  for (const it of insets) {
    if (!it.bld.length) continue; // nothing to stand in for: it would overlap its 1 m self
    const req: MeshRequest = { key: it.key, url: new URL(`data/${it.file}`, location.href).href,  // the worker resolves against its own URL
      N: it.N, s: 1, x0: 0, y0: 0, keep: false, dataOnly: false, bld: null };
    const m = await new Promise<MeshReply>((res) => { waiting.set(it.key, res); worker.postMessage(req); });
    if (m.type !== 'node') { console.warn('inset', it.key, m.error); continue; }
    if (!m.quads) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3));
    geo.setAttribute('vattr', new THREE.BufferAttribute(m.attr, 4));
    geo.setAttribute('vpal', new THREE.BufferAttribute(m.pal, 1));
    const idx = new Uint32Array(m.quads * 6);
    for (let q = 0, b = 0; q < m.quads; q++, b += 4) idx.set([b, b + 1, b + 2, b, b + 2, b + 3], q * 6);
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.computeBoundingBox(); geo.computeBoundingSphere();
    const mesh = new THREE.Mesh(geo, material);
    mesh.matrixAutoUpdate = false;
    mesh.matrix.compose(new THREE.Vector3(it.x0, 0, it.y0), new THREE.Quaternion(), new THREE.Vector3(it.r, it.r, it.r));
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.visible = false;
    scene.add(mesh);
    out.push({ ...it, mesh });
  }
  worker.terminate();
  return out;
}
