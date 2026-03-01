import type { PropsWithChildren, ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type PanelProps = PropsWithChildren<{
  title?: ReactNode;
  subtitle?: ReactNode;
  className?: string;
}>;

export default function Panel({ title, subtitle, className, children }: PanelProps) {
  return (
    <Card className={cn("panel", className)}>
      {title || subtitle ? (
        <CardHeader className="space-y-2 p-4">
          {title ? <CardTitle className="text-xl">{title}</CardTitle> : null}
          {subtitle ? <CardDescription className="subtle">{subtitle}</CardDescription> : null}
        </CardHeader>
      ) : null}
      <CardContent className={title || subtitle ? "px-4 pb-4 pt-0" : "p-4"}>{children}</CardContent>
    </Card>
  );
}
