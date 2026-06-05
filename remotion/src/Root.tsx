import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { MochienIssue, MOCHIEN_ISSUE_FRAMES } from "./mochien/MochienIssue";
import { SampleA, SAMPLE_A_FRAMES } from "./mochien/SampleA";
import { SampleB, SAMPLE_B_FRAMES } from "./mochien/SampleB";
import { SampleC, SAMPLE_C_FRAMES } from "./mochien/SampleC";
import { SampleD, SAMPLE_D_FRAMES } from "./mochien/SampleD";
import { NavyDark, NAVY_DARK_FRAMES, NavyDarkProps } from "./mochien/NavyDark";
import { IssuePoC, IssuePoCProps, IssueScene } from "./mochien/IssuePoC";
import pocRaw from "../public/slides/issue1_poc.json";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MyComp"
        component={MyComposition}
        durationInFrames={60}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="MochienIssue"
        component={MochienIssue}
        durationInFrames={MOCHIEN_ISSUE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition id="SampleA" component={SampleA} durationInFrames={SAMPLE_A_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="SampleB" component={SampleB} durationInFrames={SAMPLE_B_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="SampleC" component={SampleC} durationInFrames={SAMPLE_C_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="SampleD" component={SampleD} durationInFrames={SAMPLE_D_FRAMES} fps={30} width={1920} height={1080} />
      <Composition<NavyDarkProps> id="NavyDark" component={NavyDark} durationInFrames={NAVY_DARK_FRAMES} fps={30} width={1920} height={1080} defaultProps={{}} />
      <Composition<IssuePoCProps>
        id="IssuePoC"
        component={IssuePoC}
        durationInFrames={pocRaw.total_frames}
        fps={pocRaw.fps}
        width={1920}
        height={1080}
        defaultProps={{
          slides: pocRaw.slides as unknown as IssueScene[],
          fps: pocRaw.fps,
        }}
      />
    </>
  );
};
