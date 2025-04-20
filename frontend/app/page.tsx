'use client';
import Image from 'next/image';
import { useEffect, useState } from 'react';

export default function Home() {
	const [query, setQuery] = useState('');
	const [messages, setMessages] = useState<string[]>([]);

	useEffect(() => {
		const eventSource = new EventSource('http://localhost:8000/stream');

		eventSource.onmessage = (event) => {
			const data = JSON.parse(event.data);
			setMessages((prev) => [...prev, JSON.stringify(data)]);
		};

		return () => {
			eventSource.close();
		};
	}, []);

	const handleSubmit = async () => {
		const payload = {
			query,
			query_id: '47204a6b-8eb1-4d83-bcf1-2d7ba8cba740',
		};

		try {
			const response = await fetch('http://localhost:8000/interact', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(payload),
			});
			const data = await response.json();
			console.log('Response:', data);
		} catch (error) {
			console.error('Error:', error);
		}
	};

	return (
		<div className='h-screen flex flex-col p-4'>
			<div className='flex gap-4 mb-4'>
				<textarea
					rows={2}
					className='flex-grow p-2 border rounded resize-none'
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					placeholder='Enter your query here...'
				/>
				<button
					onClick={handleSubmit}
					className='px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600'>
					Submit
				</button>
			</div>

			<div className='flex-grow border rounded p-4 overflow-auto'>
				{messages.map((message, index) => {
					const data = JSON.parse(message);
					return (
						<div key={index} className='mb-2'>
							{data.img ? (
								<>
									<Image
										src={`data:image/png;base64,${data.img}`}
										alt='Screenshot'
										width={800}
										height={600}
										className='max-w-full h-auto mb-2'
									/>
									<div>{data.message}</div>
									<hr className='my-4' />
								</>
							) : (
								<>
									<div>
										{Object.entries(data).map(
											([key, value]) => (
												<div key={key}>
													{key}:{' '}
													{typeof value === 'object'
														? JSON.stringify(value)
														: String(value)}
												</div>
											)
										)}
									</div>
									<hr className='my-4' />
								</>
							)}
						</div>
					);
				})}
			</div>
		</div>
	);
}
