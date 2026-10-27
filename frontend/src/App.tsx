import { useState } from "react";
import MatchView from "./components/MatchView";
import RankView from "./components/RankView";

type Tab = "match" | "rank";

export default function App() {
  const [tab, setTab] = useState<Tab>("match");

  return (
    <div className="page">
      <header className="top">
        <div>
          <h1>ResuMatch</h1>
          <p className="tagline">See how a resume lines up against a job posting, requirement by requirement.</p>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "match"} onClick={() => setTab("match")}>
            Check a resume
          </button>
          <button role="tab" aria-selected={tab === "rank"} onClick={() => setTab("rank")}>
            Rank several
          </button>
        </nav>
      </header>

      {/* both stay mounted so switching tabs doesn't throw away what you pasted */}
      <div hidden={tab !== "match"}>
        <MatchView />
      </div>
      <div hidden={tab !== "rank"}>
        <RankView />
      </div>

      <footer className="foot">
        Nothing is stored. Files are parsed in memory and discarded after the response.{" "}
        <a href="https://github.com/sarvesh-raam/resumatch">Source</a>
      </footer>
    </div>
  );
}
