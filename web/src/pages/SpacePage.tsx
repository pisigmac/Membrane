import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { apiJson, Memory } from "../api";

function Points({ memories }: { memories: Memory[] }) {
  const positions = useMemo(() => {
    const arr = new Float32Array(memories.length * 3);
    memories.forEach((m, i) => {
      const emb = m.embedding;
      if (emb && emb.length >= 3) {
        arr[i * 3] = emb[0] * 8;
        arr[i * 3 + 1] = emb[1] * 8;
        arr[i * 3 + 2] = emb[2] * 8;
      } else {
        let h = 0;
        for (const c of m.id) h = (h * 31 + c.charCodeAt(0)) | 0;
        const u = ((h & 0xffff) / 0xffff) * Math.PI * 2;
        const v = (((h >> 16) & 0xffff) / 0xffff) * Math.PI;
        const r = 4 + (m.type.length % 3);
        arr[i * 3] = r * Math.sin(v) * Math.cos(u);
        arr[i * 3 + 1] = r * Math.cos(v);
        arr[i * 3 + 2] = r * Math.sin(v) * Math.sin(u);
      }
    });
    return arr;
  }, [memories]);

  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return g;
  }, [positions]);

  return (
    <points geometry={geom}>
      <pointsMaterial size={0.12} color="#c4f542" sizeAttenuation />
    </points>
  );
}

export default function SpacePage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiJson<Memory[]>("/memories")
      .then(setMemories)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <div>
      <h1 className="page-title">Memory space</h1>
      <p className="page-sub">
        Three.js point cloud from embeddings (hash fallback when stubbed) — {memories.length} memories.
      </p>
      {err && <p className="error">{err}</p>}
      <div className="viz-frame tall">
        <Canvas camera={{ position: [0, 0, 12], fov: 55 }}>
          <color attach="background" args={["#0b100e"]} />
          <ambientLight intensity={0.4} />
          <Points memories={memories} />
          <OrbitControls makeDefault />
        </Canvas>
      </div>
    </div>
  );
}
