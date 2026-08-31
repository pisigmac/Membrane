import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { apiJson, Memory } from "../api";

type Node = { id: string; label: string; type: string; group: number };
type Link = { source: string; target: string; kind: string };

export default function GraphPage() {
  const ref = useRef<SVGSVGElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const memories = await apiJson<Memory[]>("/memories");
        const contradictions = await apiJson<any[]>("/contradictions");
        if (cancelled || !ref.current) return;
        const nodes: Node[] = memories.map((m, i) => ({
          id: m.id,
          label: m.content.slice(0, 40),
          type: m.type,
          group: { fact: 1, skill: 2, preference: 3, constraint: 4 }[m.type] ?? 0,
        }));
        const idSet = new Set(nodes.map((n) => n.id));
        const links: Link[] = [];
        for (const c of contradictions) {
          if (idSet.has(c.new_id) && idSet.has(c.existing_id)) {
            links.push({ source: c.new_id, target: c.existing_id, kind: "contradiction" });
          }
        }
        for (const m of memories) {
          for (const other of m.contradicted_by || []) {
            if (idSet.has(other)) links.push({ source: m.id, target: other, kind: "contradicted_by" });
          }
        }

        const svg = d3.select(ref.current);
        svg.selectAll("*").remove();
        const width = ref.current.clientWidth || 800;
        const height = ref.current.clientHeight || 480;
        svg.attr("viewBox", `0 0 ${width} ${height}`);

        const color = d3.scaleOrdinal(d3.schemeTableau10);
        const sim = d3
          .forceSimulation(nodes as any)
          .force(
            "link",
            d3
              .forceLink(links as any)
              .id((d: any) => d.id)
              .distance(90)
          )
          .force("charge", d3.forceManyBody().strength(-180))
          .force("center", d3.forceCenter(width / 2, height / 2));

        const link = svg
          .append("g")
          .attr("stroke", "#e85d5d")
          .attr("stroke-opacity", 0.7)
          .selectAll("line")
          .data(links)
          .join("line")
          .attr("stroke-width", 1.5);

        const node = svg
          .append("g")
          .selectAll("g")
          .data(nodes)
          .join("g")
          .call(
            d3
              .drag<any, any>()
              .on("start", (event, d) => {
                if (!event.active) sim.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
              })
              .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
              })
              .on("end", (event, d) => {
                if (!event.active) sim.alphaTarget(0);
                d.fx = null;
                d.fy = null;
              }) as any
          );

        node
          .append("circle")
          .attr("r", 7)
          .attr("fill", (d) => color(String(d.group)));
        node
          .append("title")
          .text((d) => `${d.type}: ${d.label}`);

        sim.on("tick", () => {
          link
            .attr("x1", (d: any) => d.source.x)
            .attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x)
            .attr("y2", (d: any) => d.target.y);
          node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
        });
      } catch (e) {
        setErr(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1 className="page-title">Graph</h1>
      <p className="page-sub">D3 force graph — memories as nodes, contradictions as edges.</p>
      {err && <p className="error">{err}</p>}
      <div className="viz-frame tall">
        <svg ref={ref} width="100%" height="100%" />
      </div>
    </div>
  );
}
