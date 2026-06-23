import React from "react";
import "../styles/ChatMessage.css";

function ChatMessage({ message }) {
  if (message.role === "user") {
    return <div className="chat-message user-message">{message.content}</div>;
  }

  return (
    <div className="chat-message assistant-message">{message.content}</div>
  );
}

export default ChatMessage;
