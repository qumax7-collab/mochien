import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";

const BLUE = "#2B7DE9";
const BLUE_LIGHT = "#D0E4FF";
const RED = "#E50000";
const TEXT_DARK = "#1A2742";
const TEXT_LIGHT = "#8FA3BF";

const TARGET_VALUE = 159.3;
const COUNT_FRAMES = 62;
const MAX_VALUE = 200;        // ゲージスケール最大値
const MAX_ARC_DEG = 270;      // ゲージ弧の角度範囲

const SVG_W = 960;
const SVG_H = 680;
const CX = 480;
const CY = 310;
const R = 265;
const STROKE = 14;
const CIRCUMFERENCE = 2 * Math.PI * R;
const MAX_ARC_LEN = CIRCUMFERENCE * (MAX_ARC_DEG / 360);

// ゲージ弧の終点座標を計算 (12時=0°, 時計回り正)
function arcEndPoint(progress: number): { x: number; y: number } {
  const angleDeg = 225 + progress * MAX_ARC_DEG; // 12時基準の角度
  const rad = ((angleDeg - 90) * Math.PI) / 180;  // SVG座標系 (3時=0°) に変換
  return { x: CX + R * Math.cos(rad), y: CY + R * Math.sin(rad) };
}

export const NumberCard: React.FC = () => {
  const frame = useCurrentFrame();

  const value = interpolate(frame, [0, COUNT_FRAMES], [0, TARGET_VALUE], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const fadeIn = interpolate(frame, [0, 22], [0, 1], {
    extrapolateRight: "clamp",
  });

  const progress = value / MAX_VALUE;
  const arcLen = progress * MAX_ARC_LEN;
  const dot = arcEndPoint(progress);

  return (
    <AbsoluteFill
      style={{ alignItems: "center", justifyContent: "center", paddingBottom: 200 }}
    >
      <svg
        width={SVG_W}
        height={SVG_H}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{ overflow: "visible" }}
      >
        {/* USD/JPY ラベル */}
        <text
          x={CX}
          y={44}
          textAnchor="middle"
          fill={BLUE}
          fontSize={30}
          fontFamily={fontFamily}
          fontWeight={700}
          style={{ letterSpacing: "0.40em" }}
          opacity={fadeIn}
        >
          USD / JPY
        </text>

        {/* レッドアクセントライン */}
        <line
          x1={CX - 160}
          y1={62}
          x2={CX + 160}
          y2={62}
          stroke={RED}
          strokeWidth={2}
          opacity={fadeIn}
        />

        {/* トラック弧 (背景) */}
        <circle
          cx={CX}
          cy={CY}
          r={R}
          fill="none"
          stroke={BLUE_LIGHT}
          strokeWidth={STROKE}
          strokeDasharray={`${MAX_ARC_LEN} ${CIRCUMFERENCE - MAX_ARC_LEN}`}
          transform={`rotate(135 ${CX} ${CY})`}
          opacity={fadeIn}
        />

        {/* 内側の白ディスク */}
        <circle
          cx={CX}
          cy={CY}
          r={R - STROKE / 2 - 5}
          fill="rgba(255,255,255,0.60)"
          opacity={fadeIn}
        />

        {/* プログレス弧 (アニメーション) */}
        {arcLen > 0 && (
          <circle
            cx={CX}
            cy={CY}
            r={R}
            fill="none"
            stroke={BLUE}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${arcLen} ${CIRCUMFERENCE - arcLen}`}
            transform={`rotate(135 ${CX} ${CY})`}
            opacity={fadeIn}
          />
        )}

        {/* レッドマーカードット (弧の先端) */}
        <circle cx={dot.x} cy={dot.y} r={9} fill={RED} opacity={fadeIn} />
        <circle cx={dot.x} cy={dot.y} r={4} fill="#ffffff" opacity={fadeIn} />

        {/* メインナンバー */}
        <text
          x={CX}
          y={290}
          textAnchor="middle"
          fill={TEXT_DARK}
          fontSize={170}
          fontFamily={fontFamily}
          fontWeight={700}
        >
          {value.toFixed(1)}
        </text>

        {/* 円 ユニット */}
        <text
          x={CX}
          y={408}
          textAnchor="middle"
          fill={BLUE}
          fontSize={62}
          fontFamily={fontFamily}
          fontWeight={700}
          opacity={fadeIn}
        >
          円
        </text>

        {/* サブラベル */}
        <text
          x={CX}
          y={628}
          textAnchor="middle"
          fill={TEXT_LIGHT}
          fontSize={25}
          fontFamily={fontFamily}
          fontWeight={400}
          style={{ letterSpacing: "0.15em" }}
          opacity={fadeIn}
        >
          東京市場　中心値
        </text>
      </svg>
    </AbsoluteFill>
  );
};
