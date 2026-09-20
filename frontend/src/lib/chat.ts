import { getAccessToken } from './auth';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type ChatMode = 'course' | 'general';

export interface CitationSource {
  material_id: number;
  material_title: string;
  similarity_score: number;
  chunk_index: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  mode?: ChatMode;
  socraticMode?: boolean;
  grounded?: boolean;
  sources?: CitationSource[];
  interactionId?: string;
  isStreaming?: boolean;
  isThinking?: boolean;
  feedback?: 'up' | 'down' | null;
  feedbackSubmitting?: boolean;
  error?: string | null;
}

export interface StreamChatParams {
  classroomId: number;
  query: string;
  mode: ChatMode;
  socraticMode: boolean;
  topicId?: number | null;
}

export interface StreamChatCallbacks {
  onChunk: (delta: string) => void;
  onDone: (data: { grounded: boolean; sources: CitationSource[]; interaction_id: string }) => void;
  onError: (errorMsg: string) => void;
}

/**
 * Streams chat tokens from the Django ASGI SSE proxy via fetch() with a ReadableStream reader.
 */
export async function streamChat(
  params: StreamChatParams,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const token = getAccessToken();
  const endpoint = `${baseURL}/api/chat/${params.mode === 'course' ? 'course' : 'general'}/stream`;

  const payload =
    params.mode === 'course'
      ? {
          classroom_id: params.classroomId,
          topic_id: params.topicId ?? null,
          query: params.query,
          socratic_mode: params.socraticMode,
        }
      : {
          classroom_id: params.classroomId,
          query: params.query,
          socratic_mode: params.socraticMode,
        };

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err: unknown) {
    if ((err as Error)?.name === 'AbortError') {
      return;
    }
    callbacks.onError('Network connection failed. Please check your connection and try again.');
    return;
  }

  if (!response.ok) {
    let friendlyError = 'Something went wrong, please try again.';
    if (response.status === 401) {
      friendlyError = 'Your session has expired. Please refresh the page or log in again.';
    } else if (response.status === 403) {
      friendlyError = 'You do not have permission to ask questions in this classroom.';
    }
    callbacks.onError(friendlyError);
    return;
  }

  if (!response.body) {
    callbacks.onError('Unable to open response stream.');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let receivedAnyDone = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        const trimmed = block.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === 'chunk' && typeof event.delta === 'string') {
              callbacks.onChunk(event.delta);
            } else if (event.type === 'done') {
              receivedAnyDone = true;
              callbacks.onDone({
                grounded: !!event.grounded,
                sources: Array.isArray(event.sources) ? event.sources : [],
                interaction_id: event.interaction_id || '',
              });
            } else if (event.type === 'error') {
              callbacks.onError('Something went wrong, please try again.');
            }
          } catch {
            // Partial JSON buffer ignored until next boundary
          }
        }
      }
    }

    // Process trailing buffer if any
    if (buffer.trim().startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.trim().slice(6).trim());
        if (event.type === 'chunk' && typeof event.delta === 'string') {
          callbacks.onChunk(event.delta);
        } else if (event.type === 'done') {
          receivedAnyDone = true;
          callbacks.onDone({
            grounded: !!event.grounded,
            sources: Array.isArray(event.sources) ? event.sources : [],
            interaction_id: event.interaction_id || '',
          });
        }
      } catch {
        // Ignored
      }
    }

    if (!receivedAnyDone) {
      callbacks.onDone({
        grounded: false,
        sources: [],
        interaction_id: '',
      });
    }
  } catch (err: unknown) {
    if ((err as Error)?.name === 'AbortError') {
      return;
    }
    callbacks.onError('Stream was interrupted. Please try again.');
  }
}

/**
 * Submits user feedback (thumbs up / thumbs down) to the Django feedback proxy endpoint.
 */
export async function submitChatFeedback(
  interactionId: string,
  rating: 'up' | 'down',
  reason?: string
): Promise<{ status: string }> {
  const token = getAccessToken();
  const response = await fetch(`${baseURL}/api/chat/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      log_id: interactionId,
      rating,
      reason,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Failed to submit feedback: ${errorBody || response.statusText}`);
  }

  return response.json();
}
