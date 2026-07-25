export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive bg-destructive/10 text-destructive text-sm px-3 py-2">
      {message}
    </div>
  );
}
