import { AbsoluteFill, Sequence } from "remotion";
import { NumberCard } from "./NumberCard";
import { LineChart } from "./LineChart";

const BG = "#EFF2F8"; // 밝은 블루-그레이 배경
const NUMBER_CARD_FRAMES = 75;
const LINE_CHART_FRAMES = 108;

export const MOCHIEN_ISSUE_FRAMES = NUMBER_CARD_FRAMES + LINE_CHART_FRAMES;

export const MochienIssue: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <Sequence durationInFrames={NUMBER_CARD_FRAMES}>
        <NumberCard />
      </Sequence>
      <Sequence from={NUMBER_CARD_FRAMES} durationInFrames={LINE_CHART_FRAMES}>
        <LineChart />
      </Sequence>
    </AbsoluteFill>
  );
};
