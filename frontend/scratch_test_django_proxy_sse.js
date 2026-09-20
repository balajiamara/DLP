// Test SSE consumption through Django ASGI Proxy via fetch() with ReadableStream
async function testDjangoProxySSE() {
  const url = 'http://127.0.0.1:8000/api/chat/general/stream';
  const token = process.argv[2];

  console.log(`\n=================================================================`);
  console.log(`DJANGO ASGI PROXY SSE FETCH TEST`);
  console.log(`Target URL: ${url}`);
  console.log(`=================================================================\n`);

  const startTime = performance.now();
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      classroom_id: 1,
      query: 'Count from 1 to 3 with short words.',
      socratic_mode: false,
    }),
  });

  console.log(`Response status: ${response.status} ${response.statusText}`);
  console.log(`Content-Type: ${response.headers.get('content-type')}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let chunkIndex = 0;
  const arrivals = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const arrivalTime = performance.now() - startTime;
    const textChunk = decoder.decode(value, { stream: true });
    buffer += textChunk;

    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const block of lines) {
      const trimmed = block.trim();
      if (trimmed.startsWith('data: ')) {
        const jsonStr = trimmed.slice(6).trim();
        try {
          const event = JSON.parse(jsonStr);
          chunkIndex++;
          arrivals.push({ chunkIndex, arrivalTime, event });
          if (event.type === 'chunk') {
            console.log(`[T + ${arrivalTime.toFixed(1)}ms] CHUNK #${chunkIndex}: ${JSON.stringify(event.delta)}`);
          } else if (event.type === 'done') {
            console.log(`[T + ${arrivalTime.toFixed(1)}ms] DONE EVENT: grounded=${event.grounded}, interaction_id=${event.interaction_id}`);
          }
        } catch (e) {
          console.error('Failed to parse SSE event JSON:', jsonStr);
        }
      }
    }
  }

  console.log('\n--- Chunk Arrival Interval Analysis ---');
  let isProgressive = false;
  for (let i = 1; i < arrivals.length; i++) {
    const delta = arrivals[i].arrivalTime - arrivals[i - 1].arrivalTime;
    console.log(`Chunk ${i} -> Chunk ${i + 1}: interval = ${delta.toFixed(1)}ms`);
    if (delta > 20) {
      isProgressive = true;
    }
  }

  console.log(`\nVerdict: ${isProgressive ? 'SUCCESS: Progressive, non-buffered streaming confirmed through Django ASGI proxy!' : 'BUFFERED: All chunks arrived simultaneously.'}`);
}

const token = process.argv[2];
testDjangoProxySSE(token).catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
