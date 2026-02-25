import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
	title: 'Next.js App',
	description: 'Next.js 15 + TypeScript + TailwindCSS v4',
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en">
			<body className="antialiased">{children}</body>
		</html>
	);
}
