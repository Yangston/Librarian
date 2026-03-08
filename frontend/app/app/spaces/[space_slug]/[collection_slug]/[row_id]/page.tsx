"use client";

import { useParams } from "next/navigation";

import { WorkspaceRowDetailView } from "@/components/workspace/WorkspaceRowDetailView";

export default function WorkspaceRowDetailPage() {
  const params = useParams<{ space_slug: string; collection_slug: string; row_id: string }>();
  const rowId = Number.parseInt(params.row_id, 10);

  return <WorkspaceRowDetailView rowId={rowId} spaceSlug={params.space_slug} collectionSlug={params.collection_slug} />;
}
