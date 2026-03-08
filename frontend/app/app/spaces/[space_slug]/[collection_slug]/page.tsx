"use client";

import { useParams } from "next/navigation";

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

export default function CollectionWorkspacePage() {
  const params = useParams<{ space_slug: string; collection_slug: string }>();
  return <WorkspaceShell spaceSlug={params.space_slug} collectionSlug={params.collection_slug} />;
}
