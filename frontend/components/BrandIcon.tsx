import { Library } from "lucide-react";

import { cn } from "@/lib/utils";

type BrandIconProps = {
  className?: string;
  iconClassName?: string;
};

export function BrandIcon({ className, iconClassName }: Readonly<BrandIconProps>) {
  return (
    <span className={cn("brandIcon", className)} aria-hidden="true">
      <Library className={cn("h-5 w-5", iconClassName)} />
    </span>
  );
}
