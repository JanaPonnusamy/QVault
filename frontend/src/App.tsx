import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import DocumentViewer from "./pages/DocumentViewer";
import EducationAcquisition from "./pages/EducationAcquisition";
import GkScraper from "./pages/GkScraper";
import InstagramAcquisition from "./pages/InstagramAcquisition";
import Knowledge from "./pages/Knowledge";
import KnowledgeResearchHistoryPage from "./pages/KnowledgeResearchHistoryPage";
import KnowledgeResearchPage from "./pages/KnowledgeResearchPage";
import Login from "./pages/Login";
import Ncert from "./pages/Ncert";
import QuestionBank from "./pages/QuestionBank";
import Review from "./pages/Review";
import Roles from "./pages/Roles";
import SyllabusCatalog from "./pages/SyllabusCatalog";
import Users from "./pages/Users";
import VideoGeneration from "./pages/VideoGeneration";
import YouTubeExtractor from "./pages/YouTubeExtractor";
import type { ReactNode } from "react";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="d-flex vh-100 align-items-center justify-content-center">
        <div className="spinner-border text-primary" role="status" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/extractor" element={<YouTubeExtractor />} />
        <Route path="/instagram" element={<InstagramAcquisition />} />
        <Route path="/review/:jobId" element={<Review />} />
        <Route path="/ncert" element={<Ncert />} />
        <Route path="/gk-scraper" element={<GkScraper />} />
        <Route path="/education" element={<EducationAcquisition />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/documents/:id" element={<DocumentViewer />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/research" element={<KnowledgeResearchPage />} />
        <Route path="/research/history" element={<KnowledgeResearchHistoryPage />} />
        <Route path="/research/:sessionId" element={<KnowledgeResearchPage />} />
        <Route path="/videos" element={<VideoGeneration />} />
        <Route path="/catalog" element={<SyllabusCatalog />} />
        <Route path="/question-bank" element={<QuestionBank />} />
        <Route path="/users" element={<Users />} />
        <Route path="/roles" element={<Roles />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
