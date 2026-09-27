import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Bogor Agricultural Intelligence', description: 'Data-driven agricultural intelligence for Kabupaten Bogor. Official BPS data, transparent analytics.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="id"><body>{children}</body></html>;
}
