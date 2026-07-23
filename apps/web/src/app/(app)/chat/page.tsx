import { ChatView } from "@/features/chat/components/chat-view";

export default function ChatPage() {
  return (
    <section className="flex h-full flex-col gap-6">
      <h1 className="text-2xl font-semibold">Chat</h1>
      {/* min-h-0 lets this flex child shrink below its content so ChatView's
          inner regions scroll, instead of growing the page (main) itself. */}
      <div className="min-h-0 flex-1">
        <ChatView />
      </div>
    </section>
  );
}
