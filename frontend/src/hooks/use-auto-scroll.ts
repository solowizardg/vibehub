import { useCallback, useEffect, useRef } from 'react';

export function useAutoScroll<T extends HTMLElement>(deps: unknown[] = []) {
	const ref = useRef<T>(null);
	const userScrolledUp = useRef(false);

	const scrollToBottom = useCallback(() => {
		if (ref.current && !userScrolledUp.current) {
			ref.current.scrollTop = ref.current.scrollHeight;
		}
	}, []);

	useEffect(() => {
		const el = ref.current;
		if (!el) return;

		const handleScroll = () => {
			const { scrollTop, scrollHeight, clientHeight } = el;
			userScrolledUp.current = scrollHeight - scrollTop - clientHeight > 100;
		};
		el.addEventListener('scroll', handleScroll);
		return () => el.removeEventListener('scroll', handleScroll);
	}, []);

	useEffect(() => {
		scrollToBottom();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, deps);

	return { ref, scrollToBottom };
}
