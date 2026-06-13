// NavyDark: dark navy financial-terminal tone
// type "single" → 게이지 링 + 꺾은선 / type "compare" → 2시리즈 꺾은선 비교
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";
import {
  DATA as STATIC_DATA,
  LABELS as STATIC_LABELS,
  TARGET_VALUE as STATIC_TARGET,
  Y_MIN as STATIC_Y_MIN,
  Y_MAX as STATIC_Y_MAX,
  buildLinePath,
  buildAreaPath,
} from "./chartUtils";

// ── Color palette ─────────────────────────────────────────────
const BG_NAVY   = "#1B2A4A";
const RED       = "#E50000";
const WHITE     = "#FFFFFF";
const WHITE_DIM = "rgba(255,255,255,0.45)";
const WHITE_SUB = "rgba(255,255,255,0.22)";
const PANEL_BG  = "rgba(8,16,32,0.70)";
const GRID_C    = "rgba(255,255,255,0.09)";
const AXIS_C    = "rgba(255,255,255,0.35)";
const DIVIDER_C = "rgba(255,255,255,0.10)";
const TEXTURE_C = "rgba(255,255,255,0.025)";
const WHITE_LINE = "rgba(255,255,255,0.85)";

// ── Gauge constants (single モード) ───────────────────────────
const COUNT_FRAMES  = 85;
const MAX_VAL       = 200;
const R             = 195;
const CX_G          = 340;
const CY_G          = 490;
const GAUGE_STROKE  = 22;   // 게이지 링 아크 두께
const CIRC          = 2 * Math.PI * R;
const MAX_ARC       = CIRC * 0.75;

// ── Stroke & marker thickness ─────────────────────────────────
const LINE_STROKE      = 6;   // 꺾은선 두께 (single / compare s1)
const LINE_STROKE_S2   = 5;   // compare series2 선 두께
const GAUGE_DOT_OUTER  = 13;  // 게이지 끝 점 바깥 반지름
const GAUGE_DOT_INNER  = 6;   // 게이지 끝 점 안쪽 반지름
const MARKER_OUTER     = 15;  // single 끝 마커 바깥 반지름
const MARKER_INNER     = 7;   // single 끝 마커 안쪽 반지름
const MARKER_S1_OUTER  = 14;  // compare s1 마커 바깥
const MARKER_S1_INNER  = 6;   // compare s1 마커 안쪽
const MARKER_S2_OUTER  = 12;  // compare s2 마커 바깥
const MARKER_S2_INNER  = 5;   // compare s2 마커 안쪽

// ── Chart layout constants ────────────────────────────────────
const CHART_START = 8;
const CHART_END   = 115;
const CW = 760;  // single 모드 차트 너비
const CH = 420;
const OX = 60;
const OY = 16;

const STATIC_Y_TICKS = [130, 140, 150, 160];

// ── Compare 모드 레이아웃 ─────────────────────────────────────
const CMP_CW = 1350;  // compare 차트 너비 (넓게)
const CMP_CH = 480;
const CMP_OX = 70;
const CMP_OY = 20;

// ── List 모드 레이아웃 ────────────────────────────────────────
const LIST_BOX_W    = 1400;
const LIST_BOX_H    = 220;
const LIST_BOX_GAP  = 30;
const LIST_BOX_LEFT = (1920 - LIST_BOX_W) / 2;  // 260
const LIST_START_Y  = 200;
const LIST_TITLE_FS = 78;
const LIST_KW_FS    = 72;
const LIST_APPEAR   = 15;
const LIST_BOX_STARTS = [15, 35, 55] as const;

// ── Dynamic helpers ───────────────────────────────────────────
function toXDyn(i: number, n: number, w: number): number {
  return (i / (n - 1)) * w;
}
function toYDyn(v: number, h: number, yMin: number, yMax: number): number {
  return h - ((v - yMin) / (yMax - yMin)) * h;
}

// ── Props types ───────────────────────────────────────────────
export type SeriesData = {
  label:       string;
  values:      number[];
  latestValue: number;
  latestLabel: string;
};

export type ChartData = {
  type?:        "single" | "compare" | "list";
  topicId?:     string;
  titleJa:      string;
  unitLabel:    string;
  sourceLabel?: string;
  // single
  labels?:      string[];
  values?:      number[];
  yTicks?:      number[];
  latestValue?: number;
  latestLabel?: string;
  yMin?:        number;
  yMax?:        number;
  // compare
  series1?: SeriesData;
  series2?: SeriesData;
  // list
  title?:  string;
  points?: string[];
};

export type NavyDarkProps = {
  chartData?: ChartData;
};

function gaugeArcDot(prog: number): { x: number; y: number } {
  const a = ((225 + prog * 270 - 90) * Math.PI) / 180;
  return { x: CX_G + R * Math.cos(a), y: CY_G + R * Math.sin(a) };
}

export const NAVY_DARK_FRAMES = 150;

// ═══════════════════════════════════════════════════════════════
// Single モード (既存レイアウト維持)
// ═══════════════════════════════════════════════════════════════
const SingleView: React.FC<{ chartData?: ChartData; frame: number }> = ({ chartData, frame }) => {
  const data        = chartData?.values      ?? STATIC_DATA;
  const labels      = chartData?.labels      ?? STATIC_LABELS;
  const targetValue = chartData?.latestValue ?? STATIC_TARGET;
  const yMin        = chartData?.yMin        ?? STATIC_Y_MIN;
  const yMax        = chartData?.yMax        ?? STATIC_Y_MAX;
  const yTicks      = chartData?.yTicks      ?? STATIC_Y_TICKS;
  const titleJa     = chartData?.titleJa     ?? "円安の推移";
  const unitLabel   = chartData?.unitLabel   ?? "円";
  const sourceLabel = chartData?.sourceLabel ?? "";

  const pts = data.map((v, i) => ({
    x: toXDyn(i, data.length, CW),
    y: toYDyn(v, CH, yMin, yMax),
  }));
  const lp   = buildLinePath(pts);
  const ap   = buildAreaPath(pts, CH);
  const last = pts[pts.length - 1];

  const labelStep = data.length > 10 ? 3 : data.length > 6 ? 2 : 1;

  const dynRange   = yMax - yMin;
  const targetProg = dynRange > 0
    ? Math.max(0, Math.min(1, (targetValue - yMin) / dynRange))
    : 0;

  const value  = interpolate(frame, [0, COUNT_FRAMES], [0, targetValue], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.cubic),
  });
  const fi     = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: "clamp" });
  const prog   = interpolate(frame, [0, COUNT_FRAMES], [0, targetProg], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.cubic),
  });
  const arcLen = prog * MAX_ARC;
  const dot    = gaugeArcDot(prog);

  const aw = interpolate(frame, [CHART_START, CHART_END], [0, CW], {
    extrapolateRight: "clamp", extrapolateLeft: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const lo = interpolate(frame, [CHART_END, CHART_END + 12], [0, 1], {
    extrapolateRight: "clamp", extrapolateLeft: "clamp",
  });

  return (
    <>
      {/* 수직 구분선 */}
      <div style={{ position: "absolute", left: 960, top: 100, width: 1, height: 880, backgroundColor: DIVIDER_C }} />

      {/* 왼쪽: 게이지 */}
      <div style={{ position: "absolute", left: 0, top: 0, width: 960, height: 1080 }}>
        <div style={{ position: "absolute", left: 60, top: 150, width: 660, height: 720, borderRadius: 14, background: PANEL_BG, overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 6, backgroundColor: RED }} />
        </div>
        <svg width={680} height={920} viewBox="0 0 680 920" style={{ position: "absolute", left: 60, top: 40 }}>
          <text x={CX_G} y={224} textAnchor="middle" fill={WHITE_DIM} fontSize={24} fontFamily={fontFamily} fontWeight={700} style={{ letterSpacing: "0.04em" }} opacity={fi}>
            {titleJa}
          </text>
          <line x1={CX_G - 130} y1={244} x2={CX_G + 130} y2={244} stroke={RED} strokeWidth={1.5} opacity={fi} />
          <circle cx={CX_G} cy={CY_G} r={R} fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth={GAUGE_STROKE} strokeDasharray={`${MAX_ARC} ${CIRC - MAX_ARC}`} transform={`rotate(135 ${CX_G} ${CY_G})`} opacity={fi} />
          {arcLen > 0 && (
            <circle cx={CX_G} cy={CY_G} r={R} fill="none" stroke={RED} strokeWidth={GAUGE_STROKE} strokeLinecap="round" strokeDasharray={`${arcLen} ${CIRC - arcLen}`} transform={`rotate(135 ${CX_G} ${CY_G})`} opacity={fi} />
          )}
          <circle cx={dot.x} cy={dot.y} r={GAUGE_DOT_OUTER} fill={RED} opacity={fi} />
          <circle cx={dot.x} cy={dot.y} r={GAUGE_DOT_INNER} fill={WHITE} opacity={fi} />
          <text x={CX_G} y={490} textAnchor="middle" fill={WHITE} fontSize={152} fontFamily={fontFamily} fontWeight={700}>
            {value.toFixed(1)}
          </text>
          <text x={CX_G} y={584} textAnchor="middle" fill={RED} fontSize={56} fontFamily={fontFamily} fontWeight={700} opacity={fi}>
            {unitLabel}
          </text>
          <text x={CX_G} y={722} textAnchor="middle" fill={WHITE_SUB} fontSize={20} fontFamily={fontFamily} style={{ letterSpacing: "0.18em" }} opacity={fi}>
            {sourceLabel}
          </text>
        </svg>
      </div>

      {/* 오른쪽: 꺾은선 */}
      <div style={{ position: "absolute", left: 975, top: 0, width: 945, height: 1080 }}>
        <div style={{ position: "absolute", top: 140, left: 30, display: "flex", alignItems: "center", gap: 12, opacity: fi }}>
          <div style={{ width: 5, height: 36, backgroundColor: RED, borderRadius: 3 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: 38, color: WHITE, letterSpacing: "0.04em" }}>{titleJa}</span>
        </div>
        <svg width={880} height={640} viewBox="0 0 880 640" style={{ position: "absolute", left: 10, top: 196 }}>
          <defs>
            <linearGradient id="agNavy" x1={0} y1={0} x2={0} y2={CH} gradientUnits="userSpaceOnUse">
              <stop offset="0%"   stopColor={RED} stopOpacity={0.44} />
              <stop offset="60%"  stopColor={RED} stopOpacity={0.11} />
              <stop offset="100%" stopColor={RED} stopOpacity={0} />
            </linearGradient>
            <clipPath id="cpNavy"><rect x={0} y={-20} width={aw} height={CH + 40} /></clipPath>
          </defs>
          <g transform={`translate(${OX},${OY})`} opacity={fi}>
            {yTicks.map(t => {
              const y = toYDyn(t, CH, yMin, yMax);
              if (y < -5 || y > CH + 5) return null;
              return (
                <g key={t}>
                  <line x1={0} y1={y} x2={CW} y2={y} stroke={GRID_C} strokeWidth={1} />
                  <text x={-10} y={y + 5} textAnchor="end" fill={AXIS_C} fontSize={17} fontFamily={fontFamily}>{t}</text>
                </g>
              );
            })}
            <line x1={0} y1={CH} x2={CW} y2={CH} stroke={GRID_C} strokeWidth={1.5} />
            {labels.map((lb, i) => {
              const step = data.length > 10 ? 3 : data.length > 6 ? 2 : 1;
              if (i % step !== 0) return null;
              return (
                <text key={i} x={toXDyn(i, labels.length, CW)} y={CH + 30} textAnchor="middle" fill={AXIS_C} fontSize={16} fontFamily={fontFamily}>{lb}</text>
              );
            })}
          </g>
          <g transform={`translate(${OX},${OY})`}>
            <path d={ap} fill="url(#agNavy)" clipPath="url(#cpNavy)" />
            <path d={lp} fill="none" stroke={RED} strokeWidth={LINE_STROKE} strokeLinecap="round" clipPath="url(#cpNavy)" />
          </g>
          <g transform={`translate(${OX},${OY})`} opacity={lo}>
            <line x1={0} y1={last.y} x2={CW} y2={last.y} stroke={WHITE} strokeWidth={1} strokeDasharray="6 5" opacity={0.28} />
            <circle cx={last.x} cy={last.y} r={MARKER_OUTER} fill={RED} />
            <circle cx={last.x} cy={last.y} r={MARKER_INNER} fill={WHITE} />
            <rect x={last.x - 128} y={last.y - 56} width={114} height={30} rx={15} fill="rgba(8,16,32,0.90)" stroke={RED} strokeWidth={1.5} />
            <text x={last.x - 71} y={last.y - 35} textAnchor="middle" fill={WHITE} fontSize={17} fontWeight={700} fontFamily={fontFamily}>
              {value.toFixed(1)}{unitLabel}
            </text>
          </g>
        </svg>
      </div>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════
// Compare モード (2시리즈 비교: 레드 vs 화이트)
// ═══════════════════════════════════════════════════════════════
const CompareView: React.FC<{ chartData: ChartData; frame: number }> = ({ chartData, frame }) => {
  const s1 = chartData.series1!;
  const s2 = chartData.series2!;
  const labels    = chartData.labels ?? [];
  const yTicks    = chartData.yTicks ?? [];
  const yMin      = chartData.yMin   ?? 0;
  const yMax      = chartData.yMax   ?? 20;
  const unitLabel = chartData.unitLabel;
  const titleJa   = chartData.titleJa;

  const n = labels.length;
  const pts1 = s1.values.map((v, i) => ({ x: toXDyn(i, n, CMP_CW), y: toYDyn(v, CMP_CH, yMin, yMax) }));
  const pts2 = s2.values.map((v, i) => ({ x: toXDyn(i, n, CMP_CW), y: toYDyn(v, CMP_CH, yMin, yMax) }));

  const lp1   = buildLinePath(pts1);
  const ap1   = buildAreaPath(pts1, CMP_CH);
  const lp2   = buildLinePath(pts2);
  const last1 = pts1[pts1.length - 1];
  const last2 = pts2[pts2.length - 1];

  const fi = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: "clamp" });
  const aw = interpolate(frame, [CHART_START, CHART_END], [0, CMP_CW], {
    extrapolateRight: "clamp", extrapolateLeft: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const lo = interpolate(frame, [CHART_END, CHART_END + 12], [0, 1], {
    extrapolateRight: "clamp", extrapolateLeft: "clamp",
  });

  const v1Anim = interpolate(frame, [0, COUNT_FRAMES], [0, s1.latestValue], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.cubic),
  });
  const v2Anim = interpolate(frame, [0, COUNT_FRAMES], [0, s2.latestValue], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.cubic),
  });

  const labelStep = n > 20 ? 4 : n > 10 ? 3 : n > 6 ? 2 : 1;
  const zeroY     = toYDyn(0, CMP_CH, yMin, yMax);

  return (
    <>
      {/* 왼쪽: 두 수치 카드 */}
      <div style={{ position: "absolute", left: 0, top: 0, width: 430, height: 1080 }}>
        <div style={{ position: "absolute", left: 40, top: 200, width: 350, padding: "32px 28px", borderRadius: 14, background: PANEL_BG, borderLeft: `6px solid ${RED}` }}>
          <div style={{ fontFamily, fontSize: 22, color: RED, fontWeight: 700, letterSpacing: "0.08em", marginBottom: 12, opacity: fi as unknown as number }}>
            {s1.label}
          </div>
          <div style={{ fontFamily, fontSize: 96, color: WHITE, fontWeight: 700, lineHeight: 1 }}>
            {v1Anim >= 0 ? "+" : ""}{v1Anim.toFixed(1)}
          </div>
          <div style={{ fontFamily, fontSize: 32, color: RED, fontWeight: 700, marginTop: 8, opacity: fi as unknown as number }}>
            {unitLabel}
          </div>
        </div>

        <div style={{ position: "absolute", left: 40, top: 520, width: 350, height: 1, backgroundColor: DIVIDER_C }} />

        <div style={{ position: "absolute", left: 40, top: 540, width: 350, padding: "32px 28px", borderRadius: 14, background: PANEL_BG, borderLeft: `6px solid ${WHITE_LINE}` }}>
          <div style={{ fontFamily, fontSize: 22, color: WHITE_LINE, fontWeight: 700, letterSpacing: "0.08em", marginBottom: 12, opacity: fi as unknown as number }}>
            {s2.label}
          </div>
          <div style={{ fontFamily, fontSize: 96, color: WHITE_DIM, fontWeight: 700, lineHeight: 1 }}>
            {v2Anim >= 0 ? "+" : ""}{v2Anim.toFixed(1)}
          </div>
          <div style={{ fontFamily, fontSize: 32, color: WHITE_LINE, fontWeight: 700, marginTop: 8, opacity: fi as unknown as number }}>
            {unitLabel}
          </div>
        </div>
      </div>

      <div style={{ position: "absolute", left: 440, top: 80, width: 1, height: 920, backgroundColor: DIVIDER_C }} />

      {/* 오른쪽: 이중 꺾은선 차트 */}
      <div style={{ position: "absolute", left: 455, top: 0, width: 1465, height: 1080 }}>
        <div style={{ position: "absolute", top: 60, left: 30, display: "flex", alignItems: "center", gap: 12, opacity: fi as unknown as number }}>
          <div style={{ width: 5, height: 36, backgroundColor: RED, borderRadius: 3 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: 36, color: WHITE }}>{titleJa}</span>
        </div>

        <div style={{ position: "absolute", top: 120, left: 36, display: "flex", gap: 28, opacity: fi as unknown as number }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 4, backgroundColor: RED, borderRadius: 2 }} />
            <span style={{ fontFamily, fontSize: 20, color: RED, fontWeight: 700 }}>{s1.label}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 4, backgroundColor: WHITE_LINE, borderRadius: 2 }} />
            <span style={{ fontFamily, fontSize: 20, color: WHITE_LINE, fontWeight: 700 }}>{s2.label}</span>
          </div>
        </div>

        <svg width={1430} height={620} viewBox="0 0 1430 620" style={{ position: "absolute", left: 10, top: 160 }}>
          <defs>
            <linearGradient id="ag1" x1={0} y1={0} x2={0} y2={CMP_CH} gradientUnits="userSpaceOnUse">
              <stop offset="0%"   stopColor={RED} stopOpacity={0.30} />
              <stop offset="100%" stopColor={RED} stopOpacity={0} />
            </linearGradient>
            <clipPath id="cpCmp"><rect x={0} y={-20} width={aw} height={CMP_CH + 40} /></clipPath>
          </defs>

          <g transform={`translate(${CMP_OX},${CMP_OY})`} opacity={fi as unknown as number}>
            {zeroY >= 0 && zeroY <= CMP_CH && (
              <line x1={0} y1={zeroY} x2={CMP_CW} y2={zeroY} stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} strokeDasharray="4 4" />
            )}
            {yTicks.map(t => {
              const y = toYDyn(t, CMP_CH, yMin, yMax);
              if (y < -5 || y > CMP_CH + 5) return null;
              return (
                <g key={t}>
                  <line x1={0} y1={y} x2={CMP_CW} y2={y} stroke={GRID_C} strokeWidth={1} />
                  <text x={-10} y={y + 5} textAnchor="end" fill={AXIS_C} fontSize={17} fontFamily={fontFamily}>{t}{unitLabel}</text>
                </g>
              );
            })}
            <line x1={0} y1={CMP_CH} x2={CMP_CW} y2={CMP_CH} stroke={GRID_C} strokeWidth={1.5} />
            {labels.map((lb, i) => {
              if (i % labelStep !== 0) return null;
              return (
                <text key={i} x={toXDyn(i, n, CMP_CW)} y={CMP_CH + 32} textAnchor="middle" fill={AXIS_C} fontSize={16} fontFamily={fontFamily}>{lb}</text>
              );
            })}
          </g>

          <g transform={`translate(${CMP_OX},${CMP_OY})`}>
            <path d={ap1} fill="url(#ag1)" clipPath="url(#cpCmp)" />
            <path d={lp1} fill="none" stroke={RED} strokeWidth={LINE_STROKE} strokeLinecap="round" clipPath="url(#cpCmp)" />
          </g>

          <g transform={`translate(${CMP_OX},${CMP_OY})`}>
            <path d={lp2} fill="none" stroke={WHITE_LINE} strokeWidth={LINE_STROKE_S2} strokeLinecap="round" strokeDasharray="10 4" clipPath="url(#cpCmp)" />
          </g>

          <g transform={`translate(${CMP_OX},${CMP_OY})`} opacity={lo as unknown as number}>
            <circle cx={last1.x} cy={last1.y} r={MARKER_S1_OUTER} fill={RED} />
            <circle cx={last1.x} cy={last1.y} r={MARKER_S1_INNER} fill={WHITE} />
            <rect x={last1.x - 120} y={last1.y - 52} width={110} height={28} rx={14} fill="rgba(8,16,32,0.90)" stroke={RED} strokeWidth={1.5} />
            <text x={last1.x - 65} y={last1.y - 32} textAnchor="middle" fill={WHITE} fontSize={16} fontWeight={700} fontFamily={fontFamily}>
              {s1.latestValue >= 0 ? "+" : ""}{s1.latestValue.toFixed(1)}{unitLabel}
            </text>
          </g>

          <g transform={`translate(${CMP_OX},${CMP_OY})`} opacity={lo as unknown as number}>
            <circle cx={last2.x} cy={last2.y} r={MARKER_S2_OUTER} fill={WHITE_LINE} />
            <circle cx={last2.x} cy={last2.y} r={MARKER_S2_INNER} fill={BG_NAVY} />
            <rect x={last2.x - 120} y={last2.y + 14} width={110} height={28} rx={14} fill="rgba(8,16,32,0.90)" stroke={WHITE_LINE} strokeWidth={1.5} />
            <text x={last2.x - 65} y={last2.y + 34} textAnchor="middle" fill={WHITE} fontSize={16} fontWeight={700} fontFamily={fontFamily}>
              {s2.latestValue >= 0 ? "+" : ""}{s2.latestValue.toFixed(1)}{unitLabel}
            </text>
          </g>
        </svg>
      </div>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════
// List モード (3-ポイント テキスト)
// ═══════════════════════════════════════════════════════════════
const ListView: React.FC<{ chartData: ChartData; frame: number }> = ({ chartData, frame }) => {
  const title  = chartData.title  ?? chartData.titleJa ?? "";
  const points = chartData.points ?? [];

  const titleOp = interpolate(frame, [0, LIST_APPEAR], [0, 1], { extrapolateRight: "clamp" });

  return (
    <>
      <div style={{
        position: "absolute", left: LIST_BOX_LEFT, top: 70,
        width: LIST_BOX_W, opacity: titleOp,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 8, height: LIST_TITLE_FS, backgroundColor: RED, borderRadius: 4, flexShrink: 0 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: LIST_TITLE_FS, color: WHITE, letterSpacing: "0.04em" }}>
            {title}
          </span>
        </div>
        <div style={{ width: "100%", height: 2, backgroundColor: RED, marginTop: 14, opacity: 0.5 }} />
      </div>

      {points.slice(0, 3).map((point, i) => {
        const startF = LIST_BOX_STARTS[i];
        const op = interpolate(frame, [startF, startF + LIST_APPEAR], [0, 1], {
          extrapolateRight: "clamp", extrapolateLeft: "clamp",
        });
        const tx = interpolate(frame, [startF, startF + LIST_APPEAR], [-50, 0], {
          extrapolateRight: "clamp", extrapolateLeft: "clamp",
          easing: Easing.out(Easing.cubic),
        });
        const top = LIST_START_Y + i * (LIST_BOX_H + LIST_BOX_GAP);
        return (
          <div key={i} style={{
            position: "absolute",
            left: LIST_BOX_LEFT, top,
            width: LIST_BOX_W, height: LIST_BOX_H,
            opacity: op,
            transform: `translateX(${tx}px)`,
            background: PANEL_BG,
            borderRadius: 14,
            borderLeft: `8px solid ${RED}`,
            display: "flex", alignItems: "center",
            paddingLeft: 48,
          }}>
            <span style={{ fontFamily, fontWeight: 700, fontSize: LIST_KW_FS, color: WHITE, letterSpacing: "0.04em" }}>
              {point}
            </span>
          </div>
        );
      })}
    </>
  );
};

// ═══════════════════════════════════════════════════════════════
// メインコンポーネント
// ═══════════════════════════════════════════════════════════════
export const NavyDark: React.FC<NavyDarkProps> = ({ chartData }) => {
  const frame = useCurrentFrame();
  const chartType = chartData?.type ?? "single";

  return (
    <AbsoluteFill style={{ backgroundColor: BG_NAVY }}>
      <AbsoluteFill style={{
        backgroundImage: [
          `linear-gradient(${TEXTURE_C} 1px, transparent 1px)`,
          `linear-gradient(90deg, ${TEXTURE_C} 1px, transparent 1px)`,
        ].join(", "),
        backgroundSize: "64px 64px",
      }} />

      {chartType === "list"
        ? <ListView  chartData={chartData!} frame={frame} />
        : chartType === "compare" && chartData?.series1 && chartData?.series2
          ? <CompareView chartData={chartData} frame={frame} />
          : <SingleView  chartData={chartData} frame={frame} />
      }
    </AbsoluteFill>
  );
};
