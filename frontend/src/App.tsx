import { BrowserRouter, Route, Routes } from 'react-router';
import { MainLayout } from '@/components/layout/main-layout';
import { HomePage } from '@/routes/home';
import { ChatPage } from '@/routes/chat';

export default function App() {
	return (
		<BrowserRouter>
			<MainLayout>
				<Routes>
					<Route path="/" element={<HomePage />} />
					<Route path="/chat/:chatId" element={<ChatPage />} />
				</Routes>
			</MainLayout>
		</BrowserRouter>
	);
}
