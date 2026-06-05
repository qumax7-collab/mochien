// Sample C: 上段 3カード → 下段チャート 順次登場
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";
import { BLUE, RED, BG, TEXT_DARK, AXIS_COLOR, GRID_COLOR, TARGET_VALUE, LABELS, toX, toY, makePts, buildLinePath, buildAreaPath } from "./chartUtils";

const CW = 1620;
const CH = 340;
const OX = 70;
const OY = 10;
const pts = makePts(CW, CH);
const lp = buildLinePath(pts);
const ap = buildAreaPath(pts, CH);
const last = pts[pts.length - 1];

function cardFade(frame: number, delay: number) {
  return interpolate(frame, [delay, delay + 18], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
}
function cardSlide(frame: number, delay: number) {
  return interpolate(frame, [delay, delay + 18], [28, 0], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: Easing.out(Easing.cubic) });
}

export const SampleC: React.FC = () => {
  const frame = useCurrentFrame();

  const value = interpolate(frame, [10, 65], [0, TARGET_VALUE], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const aw = interpolate(frame, [55, 145], [0, CW], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: Easing.out(Easing.cubic) });
  const lo = interpolate(frame, [145, 158], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  const chartFi = interpolate(frame, [45, 65], [0, 1], { extrapolateRight: "clamp" });

  const CARD_STYLE = (delay: number): React.CSSProperties => ({
    width: 480,
    backgroundColor: "white",
    borderRadius: 16,
    padding: "28px 32px",
    boxShadow: "0 4px 24px rgba(43,125,233,0.10)",
    opacity: cardFade(frame, delay),
    transform: `translateY(${cardSlide(frame, delay)}px)`,
    position: "relative",
    overflow: "hidden",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* === 上段: 3カード === */}
      <div style={{ position: "absolute", top: 128, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 40, paddingLeft: 40, paddingRight: 40 }}>

        {/* カード1: 現在値 */}
        <div style={CARD_STYLE(0)}>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: 5, backgroundColor: BLUE, borderRadius: "16px 16px 0 0" }} />
          <div style={{ fontFamily, fontSize: 18, color: AXIS_COLOR, letterSpacing: "0.1em", marginBottom: 14, marginTop: 8 }}>現在値</div>
          <div style={{ display: "flex", alignItems: "baseline" }}>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 82, color: TEXT_DARK, lineHeight: 1, letterSpacing: "-0.02em" }}>{value.toFixed(1)}</span>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 34, color: BLUE, marginLeft: 8 }}>円</span>
          </div>
          <div style={{ fontFamily, fontSize: 16, color: AXIS_COLOR, marginTop: 10, letterSpacing: "0.08em" }}>USD / JPY　東京市場</div>
        </div>

        {/* カード2: 期間変化 */}
        <div style={CARD_STYLE(14)}>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: 5, backgroundColor: "#22C55E", borderRadius: "16px 16px 0 0" }} />
          <div style={{ fontFamily, fontSize: 18, color: AXIS_COLOR, letterSpacing: "0.1em", marginBottom: 14, marginTop: 8 }}>期間変化</div>
          <div style={{ display: "flex", alignItems: "baseline" }}>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 82, color: "#22C55E", lineHeight: 1, letterSpacing: "-0.02em" }}>+29.3</span>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 34, color: "#22C55E", marginLeft: 8 }}>円</span>
          </div>
          <div style={{ fontFamily, fontSize: 16, color: AXIS_COLOR, marginTop: 10 }}>130円 → 159.3円</div>
        </div>

        {/* カード3: 観測期間 */}
        <div style={CARD_STYLE(28)}>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: 5, backgroundColor: AXIS_COLOR, borderRadius: "16px 16px 0 0" }} />
          <div style={{ fontFamily, fontSize: 18, color: AXIS_COLOR, letterSpacing: "0.1em", marginBottom: 14, marginTop: 8 }}>観測期間</div>
          <div style={{ fontFamily, fontWeight: 700, fontSize: 44, color: TEXT_DARK, lineHeight: 1.3 }}>{'\''}23/1<br />→ \'25/5</div>
          <div style={{ fontFamily, fontSize: 16, color: AXIS_COLOR, marginTop: 10 }}>約2年3ヶ月</div>
        </div>
      </div>

      {/* === 下段: チャート === */}
      <div style={{ position: "absolute", left: 100, top: 410, right: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, opacity: chartFi }}>
          <div style={{ width: 4, height: 32, backgroundColor: BLUE, borderRadius: 2 }} />
          <span style={{ fontFamily, fontWeight: 700, fontSize: 32, color: TEXT_DARK }}>円安の推移</span>
          <div style={{ backgroundColor: BLUE, borderRadius: 20, padding: "4px 14px", marginLeft: 8 }}>
            <span style={{ fontFamily, fontWeight: 700, fontSize: 16, color: "#fff" }}>USD/JPY</span>
          </div>
        </div>
        <svg width={1720} height={430} viewBox={`0 0 1720 430`}>
          <defs>
            <linearGradient id="agC" x1={0} y1={0} x2={0} y2={CH} gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor={BLUE} stopOpacity={0.16} />
              <stop offset="100%" stopColor={BLUE} stopOpacity={0} />
            </linearGradient>
            <clipPath id="cpC"><rect x={0} y={-20} width={aw} height={CH + 40} /></clipPath>
          </defs>

          {/* 白カードパネル */}
          <rect x={OX - 20} y={-12} width={CW + 40} height={CH + 32} rx={12} fill="white" opacity={chartFi * 0.8} />

          <g transform={`translate(${OX},${OY})`} opacity={chartFi}>
            {[130, 140, 150, 160].map(t => {
              const y = toY(t, CH);
              return <g key={t}>
                <line x1={0} y1={y} x2={CW} y2={y} stroke={GRID_COLOR} strokeWidth={1} />
                <text x={-12} y={y + 5} textAnchor="end" fill={AXIS_COLOR} fontSize={16} fontFamily={fontFamily}>{t}</text>
              </g>;
            })}
            <line x1={0} y1={CH} x2={CW} y2={CH} stroke={GRID_COLOR} strokeWidth={1.5} />
            {LABELS.filter((_, i) => i % 2 === 0).map((lb, j) => (
              <text key={j} x={toX(j * 2, CW)} y={CH + 30} textAnchor="middle" fill={AXIS_COLOR} fontSize={16} fontFamily={fontFamily}>{lb}</text>
            ))}
          </g>
          <g transform={`translate(${OX},${OY})`}>
            <path d={ap} fill="url(#agC)" clipPath="url(#cpC)" />
            <path d={lp} fill="none" stroke={BLUE} strokeWidth={4} strokeLinecap="round" clipPath="url(#cpC)" />
          </g>
          <g transform={`translate(${OX},${OY})`} opacity={lo}>
            <circle cx={last.x} cy={last.y} r={11} fill={RED} />
            <circle cx={last.x} cy={last.y} r={4.5} fill="white" />
            <rect x={last.x - 122} y={last.y - 50} width={114} height={30} rx={15} fill="white" stroke={BLUE} strokeWidth={1.5} />
            <text x={last.x - 65} y={last.y - 30} textAnchor="middle" fill={TEXT_DARK} fontSize={17} fontWeight={700} fontFamily={fontFamily}>159.3円</text>
          </g>
        </svg>
      </div>
    </AbsoluteFill>
  );
};
export const SAMPLE_C_FRAMES = 165;
