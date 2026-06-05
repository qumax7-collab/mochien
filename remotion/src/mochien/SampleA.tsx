// Sample A: 左右分割 — ゲージ (左) + ライン チャート (右) 同時アニメーション
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";
import { BLUE, RED, BG, TEXT_DARK, AXIS_COLOR, GRID_COLOR, TARGET_VALUE, LABELS, toX, toY, makePts, buildLinePath, buildAreaPath } from "./chartUtils";

const COUNT_FRAMES = 80;
const CHART_START = 10;
const CHART_END = 115;

const R = 195;
const CX = 340;
const CY = 490;
const STROKE = 12;
const CIRC = 2 * Math.PI * R;
const MAX_ARC = CIRC * 0.75;
const MAX_VAL = 200;

const CW = 760;
const CH = 420;
const OX = 60;
const OY = 16;
const pts = makePts(CW, CH);
const lp = buildLinePath(pts);
const ap = buildAreaPath(pts, CH);
const last = pts[pts.length - 1];

function dotAt(prog: number) {
  const a = ((225 + prog * 270 - 90) * Math.PI) / 180;
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
}

export const SampleA: React.FC = () => {
  const frame = useCurrentFrame();
  const value = interpolate(frame, [0, COUNT_FRAMES], [0, TARGET_VALUE], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const fi = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const prog = value / MAX_VAL;
  const arcLen = prog * MAX_ARC;
  const dot = dotAt(prog);
  const aw = interpolate(frame, [CHART_START, CHART_END], [0, CW], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: Easing.out(Easing.cubic) });
  const lo = interpolate(frame, [CHART_END, CHART_END + 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* 区切り線 */}
      <div style={{ position: "absolute", left: 960, top: 80, width: 1, height: 900, backgroundColor: "#D4E4F7" }} />

      {/* 左: ゲージ */}
      <div style={{ position: "absolute", left: 0, top: 0, width: 960, height: 1080 }}>
        <svg width={680} height={960} viewBox="0 0 680 960" style={{ position: "absolute", left: 60, top: 40 }}>
          <text x={CX} y={210} textAnchor="middle" fill={BLUE} fontSize={26} fontFamily={fontFamily} fontWeight={700} style={{ letterSpacing: "0.38em" }} opacity={fi}>USD / JPY</text>
          <line x1={CX - 130} y1={228} x2={CX + 130} y2={228} stroke={RED} strokeWidth={2} opacity={fi} />

          <circle cx={CX} cy={CY} r={R} fill="none" stroke="#D0E4FF" strokeWidth={STROKE}
            strokeDasharray={`${MAX_ARC} ${CIRC - MAX_ARC}`} transform={`rotate(135 ${CX} ${CY})`} opacity={fi} />
          <circle cx={CX} cy={CY} r={R - STROKE / 2 - 4} fill="rgba(255,255,255,0.55)" opacity={fi} />
          {arcLen > 0 && <circle cx={CX} cy={CY} r={R} fill="none" stroke={BLUE} strokeWidth={STROKE} strokeLinecap="round"
            strokeDasharray={`${arcLen} ${CIRC - arcLen}`} transform={`rotate(135 ${CX} ${CY})`} opacity={fi} />}
          <circle cx={dot.x} cy={dot.y} r={8} fill={RED} opacity={fi} />
          <circle cx={dot.x} cy={dot.y} r={3.5} fill="white" opacity={fi} />

          <text x={CX} y={488} textAnchor="middle" fill={TEXT_DARK} fontSize={140} fontFamily={fontFamily} fontWeight={700}>{value.toFixed(1)}</text>
          <text x={CX} y={578} textAnchor="middle" fill={BLUE} fontSize={52} fontFamily={fontFamily} fontWeight={700} opacity={fi}>円</text>
          <text x={CX} y={700} textAnchor="middle" fill={AXIS_COLOR} fontSize={21} fontFamily={fontFamily} style={{ letterSpacing: "0.12em" }} opacity={fi}>東京市場　中心値</text>
        </svg>
      </div>

      {/* 右: チャート */}
      <div style={{ position: "absolute", left: 975, top: 0, width: 945, height: 1080 }}>
        <div style={{ position: "absolute", top: 130, left: 30, display: "flex", alignItems: "center", gap: 10, opacity: fi }}>
          <div style={{ width: 4, height: 34, backgroundColor: BLUE, borderRadius: 2 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: 36, color: TEXT_DARK }}>円安の推移</span>
        </div>
        <svg width={880} height={660} viewBox="0 0 880 660" style={{ position: "absolute", left: 10, top: 190 }}>
          <defs>
            <linearGradient id="agA" x1={0} y1={0} x2={0} y2={CH} gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor={BLUE} stopOpacity={0.16} />
              <stop offset="100%" stopColor={BLUE} stopOpacity={0} />
            </linearGradient>
            <clipPath id="cpA"><rect x={0} y={-20} width={aw} height={CH + 40} /></clipPath>
          </defs>
          <g transform={`translate(${OX},${OY})`} opacity={fi}>
            {[130, 140, 150, 160].map(t => {
              const y = toY(t, CH);
              return <g key={t}>
                <line x1={0} y1={y} x2={CW} y2={y} stroke={GRID_COLOR} strokeWidth={1} />
                <text x={-10} y={y + 5} textAnchor="end" fill={AXIS_COLOR} fontSize={17} fontFamily={fontFamily}>{t}</text>
              </g>;
            })}
            <line x1={0} y1={CH} x2={CW} y2={CH} stroke={GRID_COLOR} strokeWidth={1} />
            {LABELS.filter((_, i) => i % 3 === 0).map((lb, j) => (
              <text key={j} x={toX(j * 3, CW)} y={CH + 30} textAnchor="middle" fill={AXIS_COLOR} fontSize={16} fontFamily={fontFamily}>{lb}</text>
            ))}
          </g>
          <g transform={`translate(${OX},${OY})`}>
            <path d={ap} fill="url(#agA)" clipPath="url(#cpA)" />
            <path d={lp} fill="none" stroke={BLUE} strokeWidth={4} strokeLinecap="round" clipPath="url(#cpA)" />
          </g>
          <g transform={`translate(${OX},${OY})`} opacity={lo}>
            <circle cx={last.x} cy={last.y} r={10} fill={RED} />
            <circle cx={last.x} cy={last.y} r={4} fill="white" />
            <text x={last.x - 14} y={last.y - 18} textAnchor="end" fill={TEXT_DARK} fontSize={20} fontWeight={700} fontFamily={fontFamily}>159.3円</text>
          </g>
        </svg>
      </div>
    </AbsoluteFill>
  );
};
export const SAMPLE_A_FRAMES = 150;
