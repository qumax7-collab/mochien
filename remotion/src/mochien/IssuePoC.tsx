// IssuePoC: scene list JSON を受け取り TextSlide + NavyDark をシーケンス
// - type:"text"  → TextSlide
// - type:"chart" → NavyDark (既存コンポーネント再使用)
import { Series } from "remotion";
import { TextSlide } from "./TextSlide";
import { NavyDark, ChartData } from "./NavyDark";

// ── Scene types ───────────────────────────────────────────
export type TextScene = {
  type: "text";
  text: string;
  keywords: string[];
  duration_sec: number;
};

export type ChartScene = {
  type: "chart";
  chart_data: ChartData;
  duration_sec: number;
};

export type IssueScene = TextScene | ChartScene;

// ── Props ─────────────────────────────────────────────────
export type IssuePoCProps = {
  slides: IssueScene[];
  fps?: number;
  sectionLabel?: string;
};

// ── Component ─────────────────────────────────────────────
export const IssuePoC: React.FC<IssuePoCProps> = ({
  slides,
  fps = 30,
  sectionLabel,
}) => {
  return (
    <Series>
      {slides.map((slide, i) => {
        const frames = Math.round(slide.duration_sec * fps);

        if (slide.type === "text") {
          return (
            <Series.Sequence key={i} durationInFrames={frames}>
              <TextSlide
                text={slide.text}
                keywords={slide.keywords}
                durationInFrames={frames}
                sectionLabel={sectionLabel}
              />
            </Series.Sequence>
          );
        }

        // type === "chart"
        return (
          <Series.Sequence key={i} durationInFrames={frames}>
            <NavyDark chartData={slide.chart_data} />
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
