import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";

const BLUE = "#2B7DE9";
const RED = "#E50000";
const TEXT_DARK = "#1A2742";
const TEXT_MID = "#5A6B85";
const AXIS_COLOR = "#9BB0C9";
const GRID_COLOR = "#E4ECF7";

// PoC用サンプルデータ (円安推移の例示値 — トーン確認のみ)
const DATA = [130, 133, 137, 140, 144, 148, 151, 155, 157, 159.3];
const LABELS = ["'23/1", "'23/4", "'23/7", "'23/10", "'24/1", "'24/4", "'24/7", "'24/10", "'25/1", "'25/5"];
const Y_TICKS = [130, 135, 140, 145, 150, 155, 160, 165];
const Y_MIN = 125;
const Y_MAX = 165;
const CHART_W = 1280;
const CHART_H = 400;
const ANIM_START = 15;
const ANIM_END = 92;
const TENSION = 0.35;

const OFFSET_X = 90;
const OFFSET_Y = 20;
const SVG_W = CHART_W + OFFSET_X + 30;
const SVG_H = CHART_H + 80;

const toX = (i: number) => (i / (DATA.length - 1)) * CHART_W;
const toY = (v: number) => CHART_H - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * CHART_H;

const pts = DATA.map((v, i) => ({ x: toX(i), y: toY(v) }));
const lastPt = pts[pts.length - 1];

function buildLinePath(p: { x: number; y: number }[]): string {
  let d = `M ${p[0].x.toFixed(2)},${p[0].y.toFixed(2)}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[Math.max(0, i - 1)];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[Math.min(p.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) * TENSION;
    const cp1y = p1.y + (p2.y - p0.y) * TENSION;
    const cp2x = p2.x - (p3.x - p1.x) * TENSION;
    const cp2y = p2.y - (p3.y - p1.y) * TENSION;
    d += ` C ${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
  }
  return d;
}

const linePath = buildLinePath(pts);
const areaPath = `${linePath} L ${lastPt.x.toFixed(2)},${CHART_H} L ${pts[0].x.toFixed(2)},${CHART_H} Z`;

// 159.3のY座標 (基準線用)
const REF_Y = toY(159.3);

export const LineChart: React.FC = () => {
  const frame = useCurrentFrame();

  const titleFade = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const panelFade = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });

  const animWidth = interpolate(frame, [ANIM_START, ANIM_END], [0, CHART_W], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const labelOpacity = interpolate(frame, [ANIM_END, ANIM_END + 10], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        alignItems: "flex-start",
        paddingLeft: 130,
        paddingTop: 130,
        paddingBottom: 230,
      }}
    >
      {/* タイトル — ブルー左バー */}
      <div
        style={{
          opacity: titleFade,
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 6,
        }}
      >
        <div style={{ width: 5, height: 44, backgroundColor: BLUE, borderRadius: 3 }} />
        <span style={{ fontFamily, fontWeight: 700, fontSize: 52, color: TEXT_DARK, letterSpacing: "0.05em" }}>
          円安の推移
        </span>
        {/* DATAバッジ */}
        <div
          style={{
            backgroundColor: BLUE,
            borderRadius: 20,
            padding: "5px 14px",
            marginLeft: 12,
            opacity: titleFade,
          }}
        >
          <span style={{ fontFamily, fontWeight: 700, fontSize: 18, color: "#fff", letterSpacing: "0.08em" }}>
            USD/JPY
          </span>
        </div>
      </div>

      {/* タイトル下ライン */}
      <div style={{
        width: 340,
        height: 2,
        backgroundColor: BLUE,
        marginBottom: 26,
        opacity: titleFade,
        marginLeft: 19,
        borderRadius: 2,
      }} />

      <svg
        width={SVG_W}
        height={SVG_H}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{ overflow: "visible" }}
      >
        <defs>
          <linearGradient id="areaGrad" x1={0} y1={0} x2={0} y2={CHART_H} gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={BLUE} stopOpacity={0.18} />
            <stop offset="75%" stopColor={BLUE} stopOpacity={0.04} />
            <stop offset="100%" stopColor={BLUE} stopOpacity={0} />
          </linearGradient>
          <clipPath id="progressClip">
            <rect x={0} y={-20} width={animWidth} height={CHART_H + 40} />
          </clipPath>
        </defs>

        {/* 白いカードパネル */}
        <rect
          x={OFFSET_X - 24}
          y={-14}
          width={CHART_W + 48}
          height={CHART_H + 44}
          rx={14}
          fill="white"
          opacity={panelFade * 0.82}
        />

        {/* グリッド・軸 */}
        <g transform={`translate(${OFFSET_X}, ${OFFSET_Y})`} opacity={panelFade}>
          {Y_TICKS.map((tick) => {
            const y = toY(tick);
            if (y < -5 || y > CHART_H + 5) return null;
            return (
              <g key={tick}>
                <line x1={0} y1={y} x2={CHART_W} y2={y} stroke={GRID_COLOR} strokeWidth={1} />
                <text x={-14} y={y + 6} textAnchor="end" fill={AXIS_COLOR} fontSize={20} fontFamily={fontFamily} fontWeight={400}>
                  {tick}
                </text>
              </g>
            );
          })}
          <line x1={0} y1={CHART_H} x2={CHART_W} y2={CHART_H} stroke={GRID_COLOR} strokeWidth={2} />
          {LABELS.map((label, i) => {
            if (i % 2 !== 0) return null;
            return (
              <text key={i} x={toX(i)} y={CHART_H + 34} textAnchor="middle" fill={AXIS_COLOR} fontSize={19} fontFamily={fontFamily} fontWeight={400}>
                {label}
              </text>
            );
          })}
        </g>

        {/* グラデーション面積 + 滑らか曲線 */}
        <g transform={`translate(${OFFSET_X}, ${OFFSET_Y})`}>
          <path d={areaPath} fill="url(#areaGrad)" clipPath="url(#progressClip)" />
          <path d={linePath} fill="none" stroke={BLUE} strokeWidth={4.5} strokeLinecap="round" clipPath="url(#progressClip)" />
        </g>

        {/* 159.3基準の破線 (アニメーション完了後にフェードイン) */}
        <g transform={`translate(${OFFSET_X}, ${OFFSET_Y})`} opacity={labelOpacity * 0.55}>
          <line
            x1={0}
            y1={REF_Y}
            x2={CHART_W}
            y2={REF_Y}
            stroke={BLUE}
            strokeWidth={1.2}
            strokeDasharray="7 5"
          />
        </g>

        {/* データポイントマーカー */}
        <g transform={`translate(${OFFSET_X}, ${OFFSET_Y})`}>
          {pts.map((p, i) => {
            const isLast = i === pts.length - 1;

            if (isLast) {
              return (
                <g key={i} opacity={labelOpacity}>
                  {/* レッドドット (Mochiенブランドアクセント) */}
                  <circle cx={p.x} cy={p.y} r={13} fill={RED} />
                  <circle cx={p.x} cy={p.y} r={5.5} fill="#ffffff" />
                  {/* ピルバッジ */}
                  <rect
                    x={p.x - 132}
                    y={p.y - 58}
                    width={118}
                    height={34}
                    rx={17}
                    fill="white"
                    stroke={BLUE}
                    strokeWidth={1.5}
                  />
                  <text
                    x={p.x - 73}
                    y={p.y - 35}
                    textAnchor="middle"
                    fill={TEXT_DARK}
                    fontSize={19}
                    fontWeight={700}
                    fontFamily={fontFamily}
                  >
                    159.3円
                  </text>
                </g>
              );
            }

            const dotProg = interpolate(animWidth, [p.x - 10, p.x + 15], [0, 1], {
              extrapolateRight: "clamp",
              extrapolateLeft: "clamp",
            });

            return (
              <circle key={i} cx={p.x} cy={p.y} r={5.5} fill="white" stroke={BLUE} strokeWidth={2} opacity={dotProg * 0.85} />
            );
          })}
        </g>
      </svg>
    </AbsoluteFill>
  );
};
