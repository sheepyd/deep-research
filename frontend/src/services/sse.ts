import type { SseEvent } from "../types/research";

export async function openTaskStream(
  url: string,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(url, {
    credentials: "same-origin",
    signal
  });
  if (!response.ok || !response.body) {
    throw new Error(`Unable to open SSE stream: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const lines = part.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          data += line.slice(5).trim();
        }
      }
      if (data) {
        onEvent({ event, data: JSON.parse(data) });
      }
    }
  }
}
