import { ChatView } from "@/features/chat/components/chat-view";

export default function ChatPage() {
  return (
    <section className="flex h-full flex-col gap-6">
      <h1 className="text-2xl font-semibold">Chat</h1>
      <div className="flex-1">
        <ChatView />
      </div>
    </section>
  );
}
