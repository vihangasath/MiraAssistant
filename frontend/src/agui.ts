// Minimal AG-UI client: POST RunAgentInput, read the SSE event stream.
export type A2uiMessage = Record<string, any> & { version: "v0.9" };

export interface TurnHandlers {
  onStep?: (name: string) => void;
  onMeta?: (meta: { user_text: string; trace_id: string | null; trace_url: string | null; route: string; message_id: string }) => void;
  onText?: (messageId: string, text: string) => void;
  onA2ui?: (messageId: string, messages: A2uiMessage[]) => void;
  onError?: (message: string) => void;
}

export interface UiAction {
  name: string;
  context?: Record<string, unknown>;
}

export async function runTurn(opts: {
  threadId: string;
  visitorId: string;
  text?: string;
  action?: UiAction;
  handlers: TurnHandlers;
}): Promise<void> {
  const body = {
    threadId: opts.threadId,
    runId: crypto.randomUUID(),
    state: {},
    messages: opts.text ? [{ id: crypto.randomUUID(), role: "user", content: opts.text }] : [],
    tools: [],
    context: [],
    forwardedProps: { visitor_id: opts.visitorId, action: opts.action ?? null },
  };
  let res: Response;
  try {
    res = await fetch("/api/agui", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
    });
  } catch {
    opts.handlers.onError?.("I can't reach our server right now. Please check your connection and try again.");
    return;
  }
  if (!res.ok || !res.body) {
    opts.handlers.onError?.("Sorry, I can't answer right now. Please try again in a moment.");
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const texts: Record<string, string> = {};
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let ev: any;
      try {
        ev = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      switch (ev.type) {
        case "STEP_STARTED":
          opts.handlers.onStep?.(ev.stepName);
          break;
        case "CUSTOM":
          if (ev.name === "turn_meta") opts.handlers.onMeta?.(ev.value);
          if (ev.name === "a2ui") opts.handlers.onA2ui?.(ev.value.message_id, ev.value.messages);
          break;
        case "TEXT_MESSAGE_CONTENT":
          texts[ev.messageId] = (texts[ev.messageId] ?? "") + ev.delta;
          opts.handlers.onText?.(ev.messageId, texts[ev.messageId]);
          break;
        case "RUN_ERROR":
          opts.handlers.onError?.(ev.message);
          break;
      }
    }
  }
}
