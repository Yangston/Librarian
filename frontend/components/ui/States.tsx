import { Badge } from "@/components/ui/badge";

export function EmptyState({ message }: { message: string }) {
  return (
    <p className="muted">
      <Badge variant="outline" className="mr-2">
        Empty
      </Badge>
      {message}
    </p>
  );
}

export function LoadingState({ message }: { message: string }) {
  return (
    <p>
      <Badge variant="secondary" className="mr-2">
        Loading
      </Badge>
      {message}
    </p>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className="errorText">
      <Badge variant="destructive" className="mr-2">
        Error
      </Badge>
      {message}
    </p>
  );
}
