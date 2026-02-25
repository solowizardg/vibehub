import { Routes, Route } from 'react-router';

function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-2xl font-bold">Welcome</h1>
      <p className="mt-2 text-neutral-600">Edit src/App.tsx to get started.</p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
    </Routes>
  );
}
