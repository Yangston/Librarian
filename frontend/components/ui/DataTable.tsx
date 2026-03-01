import type { PropsWithChildren } from "react";

import { Table } from "@/components/ui/table";

export default function DataTable({ children }: PropsWithChildren) {
  return (
    <div className="tableWrap">
      <Table className="table">{children}</Table>
    </div>
  );
}
