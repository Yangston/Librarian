"use client";

import { useParams } from "next/navigation";

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

export default function SpaceWorkspacePage() {
  const params = useParams<{ space_slug: string }>();
  return <WorkspaceShell spaceSlug={params.space_slug} />;
}
