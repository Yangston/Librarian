import AppShell from "../../components/AppShell";

export default function ProductLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <AppShell>{children}</AppShell>;
}

