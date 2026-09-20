// Empirical test for Step 43b: SSE consumption via fetch() with ReadableStream
// Simulates browser client calling streaming endpoint and measuring chunk arrival times.

async function testFetchSSE() {
  const url = process.argv[2] || 'http://127.0.0.1:8021/chat/general/stream';
  const secret = process.argv[3] || 'dlp-internal-secret-key-change-me';

  console.log(`\n=================================================================`);
  console.log(`FETCH() READABLESTREAM SSE PROGRESSIVE RENDERING TEST`);
  console.log(`Target URL: ${url}`);
  console.log(`=================================================================\n`);

  const startTime = performance.now();
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': secret,
    },
    body: JSON.stringify({
      student_user_id: 3,
      classroom_id: 6,
      query: 'Count from 1 to 5 with a short word for each number.',
      socratic_mode: false,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status} ${response.statusText}`);
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
            console.log(`[T + ${arrivalTime.toFixed(1)}ms] DONE EVENT: grounded=${event.grounded}, sources=${event.sources?.length}`);
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

  console.log(`\nVerdict: ${isProgressive ? 'SUCCESS: Progressive, non-buffered streaming confirmed via fetch() ReadableStream.' : 'BUFFERED: All chunks arrived simultaneously.'}`);
}

testFetchSSE().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
