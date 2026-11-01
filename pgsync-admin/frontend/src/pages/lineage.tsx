import { createSignal, createEffect, onMount, onCleanup, Show, For } from 'solid-js';
import { apiClient } from '@/lib/api-client';

interface Node {
  id: string;
  label: string;
  type: 'source' | 'pipeline' | 'target';
  nodeType?: string;
  status?: string;
  x?: number;
  y?: number;
}

interface Edge {
  source: string;
  target: string;
  label?: string;
  style?: string;
}

interface LineageGraph {
  nodes: Node[];
  edges: Edge[];
}

function LineageCanvas(props: { nodes: Node[]; edges: Edge[] }) {
  let canvasRef: HTMLCanvasElement | undefined;
  const [selected, setSelected] = createSignal<string | null>(null);
  const [hovered, setHovered] = createSignal<string | null>(null);

  // Layout nodes in a grid
  const layoutNodes = (nodes: Node[]): Node[] => {
    const sources = nodes.filter(n => n.type === 'source');
    const pipelines = nodes.filter(n => n.type === 'pipeline');
    const targets = nodes.filter(n => n.type === 'target');

    const spacingX = 300;
    const spacingY = 100;
    const centerY = 250;

    const result: Node[] = [];

    sources.forEach((n, i) => {
      result.push({ ...n, x: 100, y: centerY + (i - (sources.length - 1) / 2) * spacingY });
    });

    pipelines.forEach((n, i) => {
      result.push({ ...n, x: 400, y: centerY + (i - (pipelines.length - 1) / 2) * spacingY });
    });

    targets.forEach((n, i) => {
      result.push({ ...n, x: 700, y: centerY + (i - (targets.length - 1) / 2) * spacingY });
    });

    return result;
  };

  const drawGraph = () => {
    const canvas = canvasRef;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;

    ctx.clearRect(0, 0, width, height);

    const laidOut = layoutNodes(props.nodes);
    const nodeMap = new Map(laidOut.map(n => [n.id, n]));

    // Draw edges
    props.edges.forEach(edge => {
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);
      if (!sourceNode || !targetNode) return;

      const sx = sourceNode.x!;
      const sy = sourceNode.y!;
      const tx = targetNode.x!;
      const ty = targetNode.y!;

      ctx.beginPath();
      ctx.strokeStyle = edge.style === 'dashed' ? '#9CA3AF' : '#6366F1';
      ctx.lineWidth = edge.style === 'dashed' ? 1.5 : 2;

      if (edge.style === 'dashed') {
        ctx.setLineDash([6, 3]);
      }

      ctx.moveTo(sx + 75, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw arrow
      const angle = Math.atan2(ty - sy, tx - (sx + 75));
      ctx.beginPath();
      ctx.fillStyle = edge.style === 'dashed' ? '#9CA3AF' : '#6366F1';
      ctx.moveTo(tx, ty);
      ctx.lineTo(tx - 10, ty - 5);
      ctx.lineTo(tx - 10, ty + 5);
      ctx.closePath();
      ctx.fill();

      // Edge label
      if (edge.label) {
        const mx = (sx + 75 + tx) / 2;
        const my = (sy + ty) / 2 - 10;
        ctx.fillStyle = '#6B7280';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(edge.label, mx, my);
      }
    });

    // Draw nodes
    laidOut.forEach(node => {
      const isSelected = selected() === node.id;
      const isHovered = hovered() === node.id;

      const x = node.x!;
      const y = node.y!;
      const w = 150;
      const h = 40;

      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 8);

      // Fill based on type
      if (node.type === 'source') {
        ctx.fillStyle = '#DCFCE7'; // green
        ctx.strokeStyle = isSelected ? '#059669' : '#86EFAC';
      } else if (node.type === 'pipeline') {
        ctx.fillStyle = '#DBEAFE'; // blue
        ctx.strokeStyle = isSelected ? '#2563EB' : '#93C5FD';
      } else {
        ctx.fillStyle = '#FEE2E2'; // red
        ctx.strokeStyle = isSelected ? '#DC2626' : '#FCA5A5';
      }

      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.fill();
      ctx.stroke();

      // Label
      ctx.fillStyle = '#1F2937';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, x + w / 2, y + h / 2);

      // Sub-label
      if (node.nodeType) {
        ctx.fillStyle = '#6B7280';
        ctx.font = '9px sans-serif';
        ctx.fillText(node.nodeType, x + w / 2, y + h - 8);
      }
    });
  };

  onMount(() => {
    drawGraph();
    window.addEventListener('resize', drawGraph);
    onCleanup(() => window.removeEventListener('resize', drawGraph));
  });

  createEffect(() => {
    props.nodes;
    props.edges;
    drawGraph();
  });

  const handleClick = (e: MouseEvent) => {
    const canvas = canvasRef;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const laidOut = layoutNodes(props.nodes);
    const clicked = laidOut.find(node => {
      return x >= node.x! && x <= node.x! + 150 && y >= node.y! && y <= node.y! + 40;
    });

    setSelected(clicked?.id || null);
  };

  const handleMouseMove = (e: MouseEvent) => {
    const canvas = canvasRef;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const laidOut = layoutNodes(props.nodes);
    const hover = laidOut.find(node => {
      return x >= node.x! && x <= node.x! + 150 && y >= node.y! && y <= node.y! + 40;
    });

    setHovered(hover?.id || null);
    canvas.style.cursor = hover ? 'pointer' : 'default';
  };

  return (
    <canvas
      ref={canvasRef}
      class="lineage-canvas"
      role="img"
      aria-label={`Data lineage graph with ${props.nodes.length} nodes and ${props.edges.length} relationships`}
      onClick={handleClick}
      onMouseMove={handleMouseMove}
    />
  );
}

export function LineagePage() {
  const [graph, setGraph] = createSignal<LineageGraph>({ nodes: [], edges: [] });
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [discovering, setDiscovering] = createSignal(false);

  const loadGraph = async () => {
    try {
      setLoading(true);
      const res = await apiClient.getLineageGraph();
      setGraph(res.data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load lineage graph');
    } finally {
      setLoading(false);
    }
  };

  const handleDiscoverAll = async () => {
    try {
      setDiscovering(true);
      await apiClient.discoverAllLineage();
      await loadGraph();
    } catch (err: any) {
      setError(err.message || 'Failed to discover lineage');
    } finally {
      setDiscovering(false);
    }
  };

  createEffect(() => {
    loadGraph();
  });

  return (
    <section class="page-stack">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">Data Lineage</h1>
        <button
          onClick={handleDiscoverAll}
          disabled={discovering()}
          class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {discovering() ? 'Discovering...' : 'Discover All'}
        </button>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error()}
        </div>
      </Show>

      <Show when={loading()}>
        <div class="text-center py-12">Loading lineage graph...</div>
      </Show>

      <Show when={!loading() && graph().nodes.length === 0}>
        <div class="text-center py-12 bg-gray-50 rounded-lg">
          <p class="text-gray-600 mb-4">No lineage data discovered</p>
          <p class="text-sm text-gray-500 mb-4">
            Click 'Discover All' to automatically detect data flow relationships
          </p>
          <button
            onClick={handleDiscoverAll}
            class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Discover All Lineage
          </button>
        </div>
      </Show>

      <Show when={!loading() && graph().nodes.length > 0}>
        <div class="lineage-layout">
          <div class="lineage-canvas-scroll">
            <div class="lineage-canvas-frame"><LineageCanvas nodes={graph().nodes} edges={graph().edges} /></div>
          </div>
          <div class="lineage-details">
            <h3 class="font-semibold text-sm mb-2">Legend</h3>
            <div class="flex items-center gap-2 text-sm">
              <div class="w-4 h-4 bg-green-200 rounded"></div>
              <span>Source (PostgreSQL)</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <div class="w-4 h-4 bg-blue-200 rounded"></div>
              <span>Pipeline (PGSync)</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <div class="w-4 h-4 bg-red-200 rounded"></div>
              <span>Target (Elasticsearch)</span>
            </div>
            <hr class="my-3" />
            <h3 class="font-semibold text-sm mb-2">Stats</h3>
            <p class="text-sm text-gray-600">
              {graph().nodes.filter(n => n.type === 'source').length} Sources
            </p>
            <p class="text-sm text-gray-600">
              {graph().nodes.filter(n => n.type === 'pipeline').length} Pipelines
            </p>
            <p class="text-sm text-gray-600">
              {graph().nodes.filter(n => n.type === 'target').length} Targets
            </p>
            <p class="text-sm text-gray-600">
              {graph().edges.length} Relationships
            </p>
          </div>
        </div>
      </Show>
    </section>
  );
}
