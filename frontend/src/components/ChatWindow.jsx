import { useEffect, useRef } from "react";

import ChatMessage from "./ChatMessage.jsx";

function ChatWindow({ messages, repository }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-8 overflow-y-auto py-8">
      {messages.map((message) => (
        <ChatMessage
          key={message.id}
          message={message}
          repository={repository}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatWindow;
