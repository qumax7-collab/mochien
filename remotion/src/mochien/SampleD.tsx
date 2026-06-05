// Sample D: ストーリー型 3ビート (アイコン→ポスター数値→チャート)
import { AbsoluteFill, Easing, Sequence, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";
import { BLUE, RED, BG, TEXT_DARK, AXIS_COLOR, GRID_COLOR, TARGET_VALUE, LABELS, toX, toY, makePts, buildLinePath, buildAreaPath } from "./chartUtils";

// ── ビート1: 上昇トレンドアイコン + テキスト ──────────────────
const Beat1: React.FC = () => {
  const frame = useCurrentFrame();
  const fi = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const arrowProgress = interpolate(frame, [8, 45], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

  // 上昇矢印の長さをアニメーション
  const arrowLen = arrowProgress * 480;

  return (
    <AbsoluteFill style={{ backgroundColor: BG, justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 80 }}>
        {/* 左: SVG矢印アイコン */}
        <svg width={240} height={520} viewBox="0 0 240 520" style={{ opacity: fi }}>
          {/* シャフト */}
          <line x1={120} y1={480} x2={120} y2={Math.max(20, 480 - arrowLen)} stroke={BLUE} strokeWidth={16} strokeLinecap="round" />
          {/* 矢印ヘッド (アニメーション完了後に表示) */}
          {arrowProgress > 0.85 && <>
            <line x1={120} y1={20} x2={60} y2={100} stroke={BLUE} strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" />
            <line x1={120} y1={20} x2={180} y2={100} stroke={BLUE} strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" />
          </>}
          {/* 小トレンドライン (背景の装飾) */}
          <polyline points="20,400 80,340 140,280 200,180 220,100" fill="none" stroke={BLUE} strokeWidth={3} strokeDasharray="6 5" opacity={0.20} />
        </svg>

        {/* 右: テキスト */}
        <div style={{ opacity: fi }}>
          <div style={{ fontFamily, fontWeight: 400, fontSize: 28, color: AXIS_COLOR, letterSpacing: "0.2em", marginBottom: 16 }}>USD / JPY</div>
          <div style={{ fontFamily, fontWeight: 700, fontSize: 80, color: TEXT_DARK, lineHeight: 1.15 }}>
            円安の<br />推移分析
          </div>
          <div style={{ width: 220, height: 4, backgroundColor: RED, marginTop: 24, marginBottom: 20, borderRadius: 2 }} />
          <div style={{ fontFamily, fontSize: 26, color: AXIS_COLOR, letterSpacing: "0.05em" }}>東京市場　中心値ベース</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── ビート2: ポスター数値 ──────────────────────────────────────
const Beat2: React.FC = () => {
  const frame = useCurrentFrame();
  const value = interpolate(frame, [0, 42], [0, TARGET_VALUE], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const fi = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const scaleIn = interpolate(frame, [0, 20], [0.88, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill style={{ backgroundColor: BG, justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
      <div style={{ opacity: fi, transform: `scale(${scaleIn})`, textAlign: "center" }}>
        <div style={{ fontFamily, fontWeight: 700, fontSize: 28, color: AXIS_COLOR, letterSpacing: "0.4em", marginBottom: 20 }}>USD / JPY 現在値</div>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center" }}>
          <span style={{ fontFamily, fontWeight: 700, fontSize: 300, color: TEXT_DARK, lineHeight: 1, letterSpacing: "-0.04em" }}>{value.toFixed(1)}</span>
          <span style={{ fontFamily, fontWeight: 700, fontSize: 110, color: BLUE, marginLeft: 24, letterSpacing: "0.02em" }}>円</span>
        </div>
        <div style={{ fontFamily, fontSize: 28, color: AXIS_COLOR, marginTop: 16, letterSpacing: "0.15em" }}>東京市場　中心値</div>
      </div>
    </AbsoluteFill>
  );
};

// ── ビート3: チャート ──────────────────────────────────────────
const CW3 = 1620;
const CH3 = 560;
const OX3 = 80;
const OY3 = 10;
const pts3 = makePts(CW3, CH3);
const lp3 = buildLinePath(pts3);
const ap3 = buildAreaPath(pts3, CH3);
const last3 = pts3[pts3.length - 1];

const Beat3: React.FC = () => {
  const frame = useCurrentFrame();
  const fi = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const aw = interpolate(frame, [8, 80], [0, CW3], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: Easing.out(Easing.cubic) });
  const lo = interpolate(frame, [80, 92], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <div style={{ position: "absolute", top: 120, left: 140, display: "flex", alignItems: "center", gap: 12, opacity: fi }}>
        <div style={{ width: 5, height: 42, backgroundColor: BLUE, borderRadius: 3 }} />
        <span style={{ fontFamily, fontWeight: 700, fontSize: 46, color: TEXT_DARK }}>円安の推移</span>
        <div style={{ backgroundColor: BLUE, borderRadius: 20, padding: "5px 16px", marginLeft: 10 }}>
          <span style={{ fontFamily, fontWeight: 700, fontSize: 18, color: "#fff" }}>USD/JPY</span>
        </div>
      </div>
      <svg width={1800} height={740} viewBox={`0 0 1800 740`} style={{ position: "absolute", left: 60, top: 188 }}>
        <defs>
          <linearGradient id="agD" x1={0} y1={0} x2={0} y2={CH3} gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={BLUE} stopOpacity={0.18} />
            <stop offset="100%" stopColor={BLUE} stopOpacity={0} />
          </linearGradient>
          <clipPath id="cpD"><rect x={0} y={-20} width={aw} height={CH3 + 40} /></clipPath>
        </defs>
        <rect x={OX3 - 22} y={-14} width={CW3 + 44} height={CH3 + 40} rx={14} fill="white" opacity={fi * 0.78} />
        <g transform={`translate(${OX3},${OY3})`} opacity={fi}>
          {[130, 135, 140, 145, 150, 155, 160, 165].map(t => {
            const y = toY(t, CH3);
            if (y < 0 || y > CH3) return null;
            return <g key={t}>
              <line x1={0} y1={y} x2={CW3} y2={y} stroke={GRID_COLOR} strokeWidth={1} />
              <text x={-12} y={y + 5} textAnchor="end" fill={AXIS_COLOR} fontSize={19} fontFamily={fontFamily}>{t}</text>
            </g>;
          })}
          <line x1={0} y1={CH3} x2={CW3} y2={CH3} stroke={GRID_COLOR} strokeWidth={1.5} />
          {LABELS.filter((_, i) => i % 2 === 0).map((lb, j) => (
            <text key={j} x={toX(j * 2, CW3)} y={CH3 + 34} textAnchor="middle" fill={AXIS_COLOR} fontSize={19} fontFamily={fontFamily}>{lb}</text>
          ))}
        </g>
        <g transform={`translate(${OX3},${OY3})`}>
          <path d={ap3} fill="url(#agD)" clipPath="url(#cpD)" />
          <path d={lp3} fill="none" stroke={BLUE} strokeWidth={5} strokeLinecap="round" clipPath="url(#cpD)" />
        </g>
        <g transform={`translate(${OX3},${OY3})`} opacity={lo}>
          <circle cx={last3.x} cy={last3.y} r={13} fill={RED} />
          <circle cx={last3.x} cy={last3.y} r={5.5} fill="white" />
          <rect x={last3.x - 128} y={last3.y - 56} width={118} height={34} rx={17} fill="white" stroke={BLUE} strokeWidth={1.5} />
          <text x={last3.x - 69} y={last3.y - 33} textAnchor="middle" fill={TEXT_DARK} fontSize={19} fontWeight={700} fontFamily={fontFamily}>159.3円</text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};

export const SampleD: React.FC = () => (
  <AbsoluteFill>
    <Sequence durationInFrames={55}><Beat1 /></Sequence>
    <Sequence from={55} durationInFrames={55}><Beat2 /></Sequence>
    <Sequence from={110} durationInFrames={65}><Beat3 /></Sequence>
  </AbsoluteFill>
);
export const SAMPLE_D_FRAMES = 175;
