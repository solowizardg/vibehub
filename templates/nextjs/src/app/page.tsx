import { Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

export default function HomePage() {
	return (
		<main className="flex min-h-screen items-center justify-center bg-neutral-50 p-8">
			<Card className="w-full max-w-xl">
				<CardHeader>
					<Badge className="w-fit" variant="secondary">
						Template Ready
					</Badge>
					<CardTitle className="mt-2 flex items-center gap-2 text-2xl">
						<Sparkles className="size-5" />
						Next.js App Router Starter
					</CardTitle>
					<CardDescription>
						Reuse components from <code>src/components/ui</code> first before creating new ones.
					</CardDescription>
				</CardHeader>
				<CardContent className="text-sm text-neutral-600">
					Edit <code>src/app/page.tsx</code> to get started. This template already includes a reusable UI kit.
				</CardContent>
				<CardFooter>
					<Button>Start Building</Button>
					<Button variant="outline">View UI Components</Button>
				</CardFooter>
			</Card>
		</main>
	);
}
