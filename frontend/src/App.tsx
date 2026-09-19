import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ReviewPage } from "./pages/ReviewPage";
import "./App.css";

function Home() {
  return (
    <div className="page-center">
      <div className="loading">Offside is running. Push something to trigger a review.</div>
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
