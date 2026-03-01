"use client";

import { Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";

import { Button, type ButtonProps } from "./button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "./dialog";

type DeleteActionButtonProps = Omit<ButtonProps, "variant"> & {
  iconOnly?: boolean;
};

export function DeleteActionButton({
  className,
  iconOnly = false,
  children,
  size,
  ...props
}: Readonly<DeleteActionButtonProps>) {
  const resolvedSize = size ?? (iconOnly ? "icon" : "sm");
  return (
    <Button
      variant="ghost"
      size={resolvedSize}
      className={cn(
        "text-destructive hover:text-destructive focus-visible:ring-destructive/40",
        iconOnly ? "h-7 w-7" : undefined,
        className
      )}
      {...props}
    >
      <Trash2 className={iconOnly ? "h-3.5 w-3.5" : "h-4 w-4"} />
      {iconOnly ? <span className="sr-only">Delete</span> : (children ?? "Delete")}
    </Button>
  );
}

type DeleteConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  onConfirm: () => void;
  isDeleting?: boolean;
  confirmLabel?: string;
};

export function DeleteConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  isDeleting = false,
  confirmLabel = "Delete"
}: Readonly<DeleteConfirmDialogProps>) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" type="button" onClick={() => onOpenChange(false)} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" type="button" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? "Deleting..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
