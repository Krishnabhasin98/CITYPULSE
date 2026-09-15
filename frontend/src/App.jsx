import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";

/**
 * Routes are lazy-loaded so the initial bundle stays small: Leaflet only ships
 * on /map and Recharts only on /city-health, instead of both loading for every page.
 */
const Home = lazy(() => import("./pages/Home"));
const LiveMap = lazy(() => import("./pages/LiveMap"));
const AreaIntelligence = lazy(() => import("./pages/AreaIntelligence"));
const CityHealth = lazy(() => import("./pages/CityHealth"));
const AuthorityDashboard = lazy(() => import("./pages/AuthorityDashboard"));
const Departments = lazy(() => import("./pages/Departments"));
const PolicyLab = lazy(() => import("./pages/PolicyLab"));
const Forecasts = lazy(() => import("./pages/Forecasts"));
const Report = lazy(() => import("./pages/Report"));
const IncidentDetail = lazy(() => import("./pages/IncidentDetail"));
const CitizenCredits = lazy(() => import("./pages/CitizenCredits"));
const Activity = lazy(() => import("./pages/Activity"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Profile = lazy(() => import("./pages/Profile"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner size={24} />
    </div>
  );
}

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Auth screens own the whole viewport. */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Everything else shares the app shell. */}
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/map" element={<LiveMap />} />
          <Route path="/area" element={<AreaIntelligence />} />
          {/* Deliberately not /health: that path belongs to the API's health probe, and
              a client route on the same URL made a hard refresh return JSON. */}
          <Route path="/city-health" element={<CityHealth />} />
          <Route path="/authority" element={<AuthorityDashboard />} />
          <Route path="/departments" element={<Departments />} />
          <Route path="/policylab" element={<PolicyLab />} />
          <Route path="/forecasts" element={<Forecasts />} />
          <Route path="/report" element={<Report />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/credits" element={<CitizenCredits />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/profile" element={<Profile />} />

          {/* Old bookmarks keep working. */}
          <Route path="/health" element={<Navigate to="/city-health" replace />} />
          <Route path="/predictive-risk" element={<Navigate to="/area" replace />} />
          <Route path="/digital-twin" element={<Navigate to="/area" replace />} />
          <Route path="/social" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
