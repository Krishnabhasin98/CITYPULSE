import {
  Activity,
  Award,
  BarChart3,
  Bot,
  Building2,
  FileText,
  Gauge,
  Home as HomeIcon,
  LineChart,
  Map,
  MapPin,
  ShieldCheck,
  TrendingUp,
  User,
} from "lucide-react";

/** Grouped navigation shared by the desktop header and the mobile drawer. */
export const NAV_SECTIONS = [
  {
    title: "Live",
    links: [
      { to: "/", label: "Home", icon: HomeIcon, short: "Home" },
      { to: "/map", label: "Incident map", icon: Map, short: "Map" },
      { to: "/area", label: "Area intelligence", icon: MapPin, short: "Area" },
      { to: "/city-health", label: "City health", icon: Gauge, short: "Health" },
    ],
  },
  {
    title: "Accountability",
    links: [
      { to: "/authority", label: "Dispatch queue", icon: ShieldCheck, short: "Queue" },
      { to: "/departments", label: "Departments", icon: Building2, short: "Depts" },
      { to: "/policylab", label: "PolicyLab", icon: FileText, short: "Policy" },
      { to: "/forecasts", label: "Forecasts", icon: LineChart, short: "Forecast" },
    ],
  },
  {
    title: "Community",
    links: [
      { to: "/report", label: "Report a problem", icon: Activity, short: "Report" },
      { to: "/credits", label: "Citizen credits", icon: Award, short: "Credits" },
      { to: "/activity", label: "My activity", icon: BarChart3, short: "Activity" },
      { to: "/assistant", label: "Civic assistant", icon: Bot, short: "Assistant" },
      { to: "/profile", label: "Profile", icon: User, short: "Profile" },
    ],
  },
];

export const ALL_LINKS = NAV_SECTIONS.flatMap((section) => section.links);

/** The five destinations that get first-class mobile tabs. */
export const MOBILE_TABS = [
  { to: "/", label: "Home", icon: HomeIcon },
  { to: "/map", label: "Map", icon: Map },
  { to: "/area", label: "Area", icon: MapPin },
  { to: "/report", label: "Report", icon: Activity },
  { to: "/city-health", label: "Health", icon: TrendingUp },
];

export const findLink = (pathname) =>
  ALL_LINKS.find((link) => (link.to === "/" ? pathname === "/" : pathname.startsWith(link.to)));
