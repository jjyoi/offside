import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ReviewPage } from "./pages/ReviewPage";
import { WHISTLE_GIF } from "./lib/gifs";
import "./App.css";

function Home() {
  return (
    <div className="page-center">
      <div className="poster">
        {WHISTLE_GIF && <img src={WHISTLE_GIF} alt="" className="poster-gif" />}
        <h1 className="poster-title">Nothing to review</h1>
        <p>Offside is running. Push something to trigger a review.</p>
        <code className="chip">git push</code>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/review/:sessionId" element={<ReviewPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
