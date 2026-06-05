export const DATA = [130, 133, 137, 140, 144, 148, 151, 155, 157, 159.3];
export const LABELS = ["'23/1", "'23/4", "'23/7", "'23/10", "'24/1", "'24/4", "'24/7", "'24/10", "'25/1", "'25/5"];
export const TARGET_VALUE = 159.3;
export const Y_MIN = 125;
export const Y_MAX = 165;

export const BLUE = "#2B7DE9";
export const RED = "#E50000";
export const BG = "#EFF2F8";
export const TEXT_DARK = "#1A2742";
export const AXIS_COLOR = "#9BB0C9";
export const GRID_COLOR = "#E4ECF7";

const TENSION = 0.35;

export const toX = (i: number, w: number) => (i / (DATA.length - 1)) * w;
export const toY = (v: number, h: number) => h - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * h;

export function makePts(w: number, h: number) {
  return DATA.map((v, i) => ({ x: toX(i, w), y: toY(v, h) }));
}

export function buildLinePath(pts: { x: number; y: number }[]): string {
  let d = `M ${pts[0].x.toFixed(2)},${pts[0].y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) * TENSION;
    const cp1y = p1.y + (p2.y - p0.y) * TENSION;
    const cp2x = p2.x - (p3.x - p1.x) * TENSION;
    const cp2y = p2.y - (p3.y - p1.y) * TENSION;
    d += ` C ${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
  }
  return d;
}

export function buildAreaPath(pts: { x: number; y: number }[], h: number): string {
  const last = pts[pts.length - 1];
  return `${buildLinePath(pts)} L ${last.x.toFixed(2)},${h} L ${pts[0].x.toFixed(2)},${h} Z`;
}
