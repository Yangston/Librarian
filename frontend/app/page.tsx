import type { Metadata } from "next";

import { LandingPage } from "../components/marketing/LandingPage";

export const metadata: Metadata = {
  title: "Librarian | Structured Knowledge Workspace",
  description:
    "Turn conversations into structured, source-linked knowledge with a premium workspace built for trust, search, and explainability.",
};

export default function HomePage() {
  return <LandingPage />;
}
