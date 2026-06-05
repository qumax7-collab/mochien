// TextSlide: navy_dark 배경 텍스트 슬라이드 (1920×1080)
// - 문장 페이드인 + 키워드 WHITE→RED 지연 전환
// - 하단 진행바 (슬라이드 체류 동안 좌→우)
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "./fonts";

// ── Color palette (NavyDark 공유) ────────────────────────
const BG_NAVY   = "#1B2A4A";
const RED       = "#E50000";
const WHITE     = "#FFFFFF";
const WHITE_DIM = "rgba(255,255,255,0.40)";
const TEXTURE_C = "rgba(255,255,255,0.025)";

// ── Animation keyframes ───────────────────────────────────
const FADE_IN_END = 18; // 텍스트 페이드인 완료 (0.6s)
const KW_START    = 22; // 키워드 색전환 시작
const KW_END      = 30; // 키워드 색전환 완료 (WHITE→RED)

// WHITE(255,255,255) → RED(229,0,0) 직선 보간
function blendToRed(t: number): string {
  const r = Math.round(255 + (229 - 255) * t);
  const g = Math.round(255 * (1 - t));
  const b = Math.round(255 * (1 - t));
  return `rgb(${r},${g},${b})`;
}

// ── Keyword 하이라이트 ────────────────────────────────────
type HLTextProps = {
  text: string;
  keywords: string[];
  kwColor: string;
};

function HighlightedText({ text, keywords, kwColor }: HLTextProps) {
  if (!keywords.length) return <>{text}</>;

  const escaped = keywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${escaped.join("|")})`, "g");
  const parts = text.split(re);

  return (
    <>
      {parts.map((part, i) =>
        keywords.includes(part) ? (
          <span key={i} style={{ color: kwColor }}>
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

// ── Props ─────────────────────────────────────────────────
export type TextSlideProps = {
  text: string;
  keywords: string[];
  durationInFrames: number;
  sectionLabel?: string;
};

// ── Component ─────────────────────────────────────────────
export const TextSlide: React.FC<TextSlideProps> = ({
  text,
  keywords,
  durationInFrames,
  sectionLabel = "円安の推移",
}) => {
  const frame = useCurrentFrame();

  // テキスト フェードイン
  const textOpacity = interpolate(frame, [0, FADE_IN_END], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const translateY = interpolate(frame, [0, FADE_IN_END], [14, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // キーワード 色変換
  const kwT = interpolate(frame, [KW_START, KW_END], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  const kwColor = blendToRed(kwT);

  // プログレスバー
  const progressPct = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG_NAVY, fontFamily }}>
      {/* 미세 그리드 텍스처 */}
      <AbsoluteFill
        style={{
          backgroundImage: [
            `linear-gradient(${TEXTURE_C} 1px, transparent 1px)`,
            `linear-gradient(90deg, ${TEXTURE_C} 1px, transparent 1px)`,
          ].join(", "),
          backgroundSize: "64px 64px",
        }}
      />

      {/* 상단 바: 레드 악센트 + 섹션 레이블 */}
      <div
        style={{
          position: "absolute",
          top: 0, left: 0, right: 0, height: 90,
          display: "flex", alignItems: "center",
          padding: "0 60px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div
          style={{
            width: 5, height: 40, borderRadius: 3,
            backgroundColor: RED, marginRight: 18, flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily, fontWeight: 700, fontSize: 22,
            color: WHITE_DIM, letterSpacing: "0.18em",
          }}
        >
          {sectionLabel}
        </span>
      </div>

      {/* 중앙 텍스트 영역 */}
      <div
        style={{
          position: "absolute",
          top: 90, bottom: 20, left: 0, right: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: "0 180px",
        }}
      >
        <div
          style={{
            opacity: textOpacity,
            transform: `translateY(${translateY}px)`,
            textAlign: "center",
            fontFamily,
            fontWeight: 700,
            fontSize: 72,
            color: WHITE,
            lineHeight: 1.55,
          }}
        >
          <HighlightedText text={text} keywords={keywords} kwColor={kwColor} />
        </div>
      </div>

      {/* 하단 진행바: 슬라이드 체류 시간 전체 */}
      <div
        style={{
          position: "absolute",
          bottom: 0, left: 0, height: 8,
          width: `${progressPct * 100}%`,
          backgroundColor: RED,
          borderRadius: "0 4px 0 0",
        }}
      />
    </AbsoluteFill>
  );
};
