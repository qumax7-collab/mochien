// Sample B: フルスクリーンチャート + 数値オーバーレイカード
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";
import { BLUE, RED, BG, TEXT_DARK, AXIS_COLOR, GRID_COLOR, TARGET_VALUE, LABELS, toX, toY, makePts, buildLinePath, buildAreaPath } from "./chartUtils";

const COUNT_FRAMES = 70;
const CHART_START = 5;
const CHART_END = 110;

const CW = 1680;
const CH = 680;
const OX = 80;
const OY = 10;
const pts = makePts(CW, CH);
const lp = buildLinePath(pts);
const ap = buildAreaPath(pts, CH);
const last = pts[pts.length - 1];

export const SampleB: React.FC = () => {
  const frame = useCurrentFrame();
  const value = interpolate(frame, [0, COUNT_FRAMES], [0, TARGET_VALUE], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const fi = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const aw = interpolate(frame, [CHART_START, CHART_END], [0, CW], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: Easing.out(Easing.cubic) });
  const lo = interpolate(frame, [CHART_END, CHART_END + 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* フルスクリーンチャート */}
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", left: 0, top: 0 }}>
        <defs>
          <linearGradient id="agB" x1={0} y1={0} x2={0} y2={CH} gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={BLUE} stopOpacity={0.14} />
            <stop offset="85%" stopColor={BLUE} stopOpacity={0.03} />
            <stop offset="100%" stopColor={BLUE} stopOpacity={0} />
          </linearGradient>
          <clipPath id="cpB"><rect x={0} y={-20} width={aw} height={CH + 40} /></clipPath>
        </defs>

        {/* チャートエリア */}
        <g transform={`translate(${100 + OX}, ${170 + OY})`} opacity={fi}>
          {[130, 135, 140, 145, 150, 155, 160, 165].map(t => {
            const y = toY(t, CH);
            if (y < 0 || y > CH) return null;
            return <g key={t}>
              <line x1={0} y1={y} x2={CW} y2={y} stroke={GRID_COLOR} strokeWidth={1} />
              <text x={-12} y={y + 5} textAnchor="end" fill={AXIS_COLOR} fontSize={19} fontFamily={fontFamily}>{t}</text>
            </g>;
          })}
          <line x1={0} y1={CH} x2={CW} y2={CH} stroke={GRID_COLOR} strokeWidth={1.5} />
          {LABELS.filter((_, i) => i % 2 === 0).map((lb, j) => (
            <text key={j} x={toX(j * 2, CW)} y={CH + 34} textAnchor="middle" fill={AXIS_COLOR} fontSize={18} fontFamily={fontFamily}>{lb}</text>
          ))}
        </g>
        <g transform={`translate(${100 + OX}, ${170 + OY})`}>
          <path d={ap} fill="url(#agB)" clipPath="url(#cpB)" />
          <path d={lp} fill="none" stroke={BLUE} strokeWidth={5} strokeLinecap="round" clipPath="url(#cpB)" />
        </g>

        {/* 最終点 */}
        <g transform={`translate(${100 + OX}, ${170 + OY})`} opacity={lo}>
          <circle cx={last.x} cy={last.y} r={13} fill={RED} />
          <circle cx={last.x} cy={last.y} r={5.5} fill="white" />
          {/* ピルバッジ */}
          <rect x={last.x - 126} y={last.y - 56} width={120} height={34} rx={17} fill="white" stroke={BLUE} strokeWidth={1.5} />
          <text x={last.x - 66} y={last.y - 33} textAnchor="middle" fill={TEXT_DARK} fontSize={19} fontWeight={700} fontFamily={fontFamily}>159.3円</text>
          {/* 破線 */}
          <line x1={0} y1={last.y} x2={last.x - 14} y2={last.y} stroke={BLUE} strokeWidth={1} strokeDasharray="6 4" opacity={0.45} />
        </g>

        {/* チャートタイトル (右上) */}
        <text x={1780} y={152} textAnchor="end" fill={AXIS_COLOR} fontSize={22} fontFamily={fontFamily} fontWeight={400} opacity={fi}>円安の推移　USD/JPY</text>
      </svg>

      {/* 数値オーバーレイカード (左上) */}
      <div style={{
        position: "absolute", left: 120, top: 145,
        backgroundColor: "white",
        borderLeft: `6px solid ${BLUE}`,
        boxShadow: "0 6px 32px rgba(43,125,233,0.13)",
        padding: "22px 44px 22px 36px",
        opacity: fi,
      }}>
        <div style={{ fontFamily, fontSize: 20, color: AXIS_COLOR, letterSpacing: "0.35em", marginBottom: 6 }}>USD / JPY</div>
        <div style={{ display: "flex", alignItems: "baseline" }}>
          <span style={{ fontFamily, fontWeight: 700, fontSize: 110, color: TEXT_DARK, lineHeight: 1, letterSpacing: "-0.02em" }}>{value.toFixed(1)}</span>
          <span style={{ fontFamily, fontWeight: 700, fontSize: 46, color: BLUE, marginLeft: 10 }}>円</span>
        </div>
        <div style={{ fontFamily, fontSize: 18, color: AXIS_COLOR, marginTop: 6, letterSpacing: "0.1em" }}>東京市場　中心値</div>
        <div style={{ width: "100%", height: 2, backgroundColor: RED, marginTop: 14, opacity: 0.8 }} />
      </div>
    </AbsoluteFill>
  );
};
export const SAMPLE_B_FRAMES = 120;
