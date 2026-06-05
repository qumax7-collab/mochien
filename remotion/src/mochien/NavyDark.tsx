// NavyDark: dark navy financial-terminal tone
// Props あり → 実データ / Props なし → chartUtils 静的データ fallback (PoC 動作保持)
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

// ── Color palette ────────────────────────────────────────────
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

// ── Gauge constants ──────────────────────────────────────────
const COUNT_FRAMES = 85;
const MAX_VAL = 200;    // ゲージスケール最大値 (USD/JPY 用固定)
const R       = 195;
const CX_G    = 340;
const CY_G    = 490;
const STROKE  = 13;
const CIRC    = 2 * Math.PI * R;
const MAX_ARC = CIRC * 0.75;

// ── Chart layout constants ───────────────────────────────────
const CHART_START = 8;
const CHART_END   = 115;
const CW = 760;
const CH = 420;
const OX = 60;
const OY = 16;

// ── Fallback Y ticks (静的データ用) ─────────────────────────
const STATIC_Y_TICKS = [130, 140, 150, 160];

// ── Dynamic helpers (chartUtils の toX/toY は静的 Y_MIN/Y_MAX 固定のため不使用) ──
function toXDyn(i: number, n: number, w: number): number {
  return (i / (n - 1)) * w;
}
function toYDyn(v: number, h: number, yMin: number, yMax: number): number {
  return h - ((v - yMin) / (yMax - yMin)) * h;
}

// ── Props type ───────────────────────────────────────────────
export type ChartData = {
  topicId:     string;
  titleJa:     string;
  unitLabel:   string;
  sourceLabel: string;
  labels:      string[];
  values:      number[];
  yTicks:      number[];
  latestValue: number;
  latestLabel: string;
  yMin:        number;
  yMax:        number;
};

export type NavyDarkProps = {
  chartData?: ChartData;
};

function gaugeArcDot(prog: number): { x: number; y: number } {
  const a = ((225 + prog * 270 - 90) * Math.PI) / 180;
  return { x: CX_G + R * Math.cos(a), y: CY_G + R * Math.sin(a) };
}

export const NAVY_DARK_FRAMES = 150;

export const NavyDark: React.FC<NavyDarkProps> = ({ chartData }) => {
  const frame = useCurrentFrame();

  // ── データ選択 (props → fallback) ──────────────────────────
  const data        = chartData?.values      ?? STATIC_DATA;
  const labels      = chartData?.labels      ?? STATIC_LABELS;
  const targetValue = chartData?.latestValue ?? STATIC_TARGET;
  const yMin        = chartData?.yMin        ?? STATIC_Y_MIN;
  const yMax        = chartData?.yMax        ?? STATIC_Y_MAX;
  const yTicks      = chartData?.yTicks      ?? STATIC_Y_TICKS;
  const titleJa     = chartData?.titleJa     ?? "円安の推移";
  const unitLabel   = chartData?.unitLabel   ?? "円";
  const sourceLabel = chartData?.sourceLabel ?? "東京市場　中心値";

  // ── 동적 차트 포인트 계산 ────────────────────────────────
  const pts = data.map((v, i) => ({
    x: toXDyn(i, data.length, CW),
    y: toYDyn(v, CH, yMin, yMax),
  }));
  const lp   = buildLinePath(pts);
  const ap   = buildAreaPath(pts, CH);
  const last = pts[pts.length - 1];

  // X축 라벨 표시 간격: 포인트 수에 따라 자동
  const labelStep = data.length > 10 ? 3 : data.length > 6 ? 2 : 1;

  // ── Gauge 애니메이션 ──────────────────────────────────────
  const value  = interpolate(frame, [0, COUNT_FRAMES], [0, targetValue], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const fi     = interpolate(frame, [0, 22], [0, 1], { extrapolateRight: "clamp" });
  const prog   = value / MAX_VAL;
  const arcLen = prog * MAX_ARC;
  const dot    = gaugeArcDot(prog);

  // ── Chart 애니메이션 ──────────────────────────────────────
  const aw = interpolate(frame, [CHART_START, CHART_END], [0, CW], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const lo = interpolate(frame, [CHART_END, CHART_END + 12], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG_NAVY }}>
      {/* 미세 그리드 텍스처 */}
      <AbsoluteFill style={{
        backgroundImage: [
          `linear-gradient(${TEXTURE_C} 1px, transparent 1px)`,
          `linear-gradient(90deg, ${TEXTURE_C} 1px, transparent 1px)`,
        ].join(", "),
        backgroundSize: "64px 64px",
      }} />

      {/* 수직 구분선 */}
      <div style={{
        position: "absolute", left: 960, top: 100,
        width: 1, height: 880, backgroundColor: DIVIDER_C,
      }} />

      {/* ═══════════════════════════
           왼쪽: 게이지 링 + 숫자
      ═══════════════════════════ */}
      <div style={{ position: "absolute", left: 0, top: 0, width: 960, height: 1080 }}>
        {/* 반투명 패널 + 빨간 사이드바 */}
        <div style={{
          position: "absolute", left: 60, top: 150, width: 660, height: 720,
          borderRadius: 14, background: PANEL_BG, overflow: "hidden",
        }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 6, backgroundColor: RED }} />
        </div>

        <svg width={680} height={920} viewBox="0 0 680 920"
          style={{ position: "absolute", left: 60, top: 40 }}>

          {/* 타이포 위계 1: USD/JPY — dim, 글자 간격 넓게 */}
          <text x={CX_G} y={224} textAnchor="middle"
            fill={WHITE_DIM} fontSize={24} fontFamily={fontFamily} fontWeight={700}
            style={{ letterSpacing: "0.43em" }} opacity={fi}>
            USD / JPY
          </text>
          <line x1={CX_G - 130} y1={244} x2={CX_G + 130} y2={244}
            stroke={RED} strokeWidth={1.5} opacity={fi} />

          {/* 트랙 호 (배경) */}
          <circle cx={CX_G} cy={CY_G} r={R} fill="none"
            stroke="rgba(255,255,255,0.09)" strokeWidth={STROKE}
            strokeDasharray={`${MAX_ARC} ${CIRC - MAX_ARC}`}
            transform={`rotate(135 ${CX_G} ${CY_G})`} opacity={fi} />

          {/* 프로그레스 호 — 레드 */}
          {arcLen > 0 && (
            <circle cx={CX_G} cy={CY_G} r={R} fill="none"
              stroke={RED} strokeWidth={STROKE} strokeLinecap="round"
              strokeDasharray={`${arcLen} ${CIRC - arcLen}`}
              transform={`rotate(135 ${CX_G} ${CY_G})`} opacity={fi} />
          )}
          <circle cx={dot.x} cy={dot.y} r={9} fill={RED} opacity={fi} />
          <circle cx={dot.x} cy={dot.y} r={4} fill={WHITE} opacity={fi} />

          {/* 타이포 위계 2: 메인 숫자 — 흰색, 크게 */}
          <text x={CX_G} y={490} textAnchor="middle"
            fill={WHITE} fontSize={152} fontFamily={fontFamily} fontWeight={700}>
            {value.toFixed(1)}
          </text>

          {/* 타이포 위계 3: 단위 — 레드 */}
          <text x={CX_G} y={584} textAnchor="middle"
            fill={RED} fontSize={56} fontFamily={fontFamily} fontWeight={700} opacity={fi}>
            {unitLabel}
          </text>

          {/* 타이포 위계 4: 출처 — 가장 작고 흐리게 */}
          <text x={CX_G} y={722} textAnchor="middle"
            fill={WHITE_SUB} fontSize={20} fontFamily={fontFamily}
            style={{ letterSpacing: "0.18em" }} opacity={fi}>
            {sourceLabel}
          </text>
        </svg>
      </div>

      {/* ═══════════════════════════
           오른쪽: 꺾은선 차트
      ═══════════════════════════ */}
      <div style={{ position: "absolute", left: 975, top: 0, width: 945, height: 1080 }}>
        {/* 타이틀 행 */}
        <div style={{
          position: "absolute", top: 140, left: 30,
          display: "flex", alignItems: "center", gap: 12, opacity: fi,
        }}>
          <div style={{ width: 5, height: 36, backgroundColor: RED, borderRadius: 3 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: 38, color: WHITE, letterSpacing: "0.04em" }}>
            {titleJa}
          </span>
          <div style={{
            backgroundColor: "rgba(229,0,0,0.18)",
            border: "1px solid rgba(229,0,0,0.55)",
            borderRadius: 20, padding: "3px 13px", marginLeft: 8,
          }}>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 16, color: RED, letterSpacing: "0.08em" }}>
              USD/JPY
            </span>
          </div>
        </div>

        <svg width={880} height={640} viewBox="0 0 880 640"
          style={{ position: "absolute", left: 10, top: 196 }}>
          <defs>
            <linearGradient id="agNavy" x1={0} y1={0} x2={0} y2={CH} gradientUnits="userSpaceOnUse">
              <stop offset="0%"   stopColor={RED} stopOpacity={0.44} />
              <stop offset="60%"  stopColor={RED} stopOpacity={0.11} />
              <stop offset="100%" stopColor={RED} stopOpacity={0} />
            </linearGradient>
            <clipPath id="cpNavy">
              <rect x={0} y={-20} width={aw} height={CH + 40} />
            </clipPath>
          </defs>

          {/* 그리드 & Y축 */}
          <g transform={`translate(${OX},${OY})`} opacity={fi}>
            {yTicks.map(t => {
              const y = toYDyn(t, CH, yMin, yMax);
              if (y < -5 || y > CH + 5) return null;
              return (
                <g key={t}>
                  <line x1={0} y1={y} x2={CW} y2={y} stroke={GRID_C} strokeWidth={1} />
                  <text x={-10} y={y + 5} textAnchor="end"
                    fill={AXIS_C} fontSize={17} fontFamily={fontFamily}>{t}</text>
                </g>
              );
            })}
            <line x1={0} y1={CH} x2={CW} y2={CH} stroke={GRID_C} strokeWidth={1.5} />

            {/* X축 라벨 — labelStep 간격 */}
            {labels.map((lb, i) => {
              if (i % labelStep !== 0) return null;
              return (
                <text key={i} x={toXDyn(i, labels.length, CW)} y={CH + 30} textAnchor="middle"
                  fill={AXIS_C} fontSize={16} fontFamily={fontFamily}>
                  {lb}
                </text>
              );
            })}
          </g>

          {/* 다크레드 그라데이션 면적 + Catmull-Rom 레드 곡선 */}
          <g transform={`translate(${OX},${OY})`}>
            <path d={ap} fill="url(#agNavy)" clipPath="url(#cpNavy)" />
            <path d={lp} fill="none" stroke={RED} strokeWidth={4}
              strokeLinecap="round" clipPath="url(#cpNavy)" />
          </g>

          {/* 흰 점 순차 등장 */}
          <g transform={`translate(${OX},${OY})`}>
            {pts.slice(0, -1).map((p, i) => {
              const dp = interpolate(aw, [p.x - 8, p.x + 12], [0, 1], {
                extrapolateRight: "clamp", extrapolateLeft: "clamp",
              });
              return <circle key={i} cx={p.x} cy={p.y} r={4} fill={WHITE} opacity={dp * 0.60} />;
            })}
          </g>

          {/* 최종점: 빨간 닷 + 파선 + 라벨 배지 */}
          <g transform={`translate(${OX},${OY})`} opacity={lo}>
            <line x1={0} y1={last.y} x2={CW} y2={last.y}
              stroke={WHITE} strokeWidth={1} strokeDasharray="6 5" opacity={0.28} />
            <circle cx={last.x} cy={last.y} r={11} fill={RED} />
            <circle cx={last.x} cy={last.y} r={5}  fill={WHITE} />
            <rect x={last.x - 128} y={last.y - 56} width={114} height={30}
              rx={15} fill="rgba(8,16,32,0.90)" stroke={RED} strokeWidth={1.5} />
            <text x={last.x - 71} y={last.y - 35} textAnchor="middle"
              fill={WHITE} fontSize={17} fontWeight={700} fontFamily={fontFamily}>
              {value.toFixed(1)}{unitLabel}
            </text>
          </g>
        </svg>
      </div>
    </AbsoluteFill>
  );
};
