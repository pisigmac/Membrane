import { useEffect, useRef } from "react";
import p5 from "p5";

type Props = {
  recordCount: number;
  pending: number;
  unresolved: number;
  ok: boolean;
};

export default function HealthViz({ recordCount, pending, unresolved, ok }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!host.current) return;
    const el = host.current;
    const sketch = (s: p5) => {
      let particles: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
      s.setup = () => {
        const w = el.clientWidth || 400;
        const h = el.clientHeight || 320;
        s.createCanvas(w, h);
        const n = Math.min(80, 12 + recordCount);
        particles = Array.from({ length: n }, () => ({
          x: s.random(w),
          y: s.random(h),
          vx: s.random(-0.6, 0.6),
          vy: s.random(-0.6, 0.6),
          r: s.random(2, 5),
        }));
      };
      s.draw = () => {
        s.background(11, 16, 14, 40);
        const accent = ok ? s.color(196, 245, 66, 180) : s.color(232, 93, 93, 180);
        const warn = s.color(240, 180, 41, 160);
        for (const p of particles) {
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < 0 || p.x > s.width) p.vx *= -1;
          if (p.y < 0 || p.y > s.height) p.vy *= -1;
          s.noStroke();
          s.fill(accent);
          s.circle(p.x, p.y, p.r * 2);
        }
        // pending / unresolved pulses
        for (let i = 0; i < pending; i++) {
          const a = s.frameCount * 0.02 + i;
          s.noFill();
          s.stroke(warn);
          s.circle(s.width * 0.3, s.height * 0.5, 40 + (i + 1) * 18 + s.sin(a) * 6);
        }
        for (let i = 0; i < unresolved; i++) {
          const a = s.frameCount * 0.03 + i;
          s.noFill();
          s.stroke(232, 93, 93, 140);
          s.circle(s.width * 0.7, s.height * 0.5, 30 + (i + 1) * 16 + s.cos(a) * 5);
        }
      };
      s.windowResized = () => {
        s.resizeCanvas(el.clientWidth, el.clientHeight);
      };
    };
    const inst = new p5(sketch, el);
    return () => {
      inst.remove();
    };
  }, [recordCount, pending, unresolved, ok]);

  return <div ref={host} style={{ width: "100%", height: "100%" }} />;
}
