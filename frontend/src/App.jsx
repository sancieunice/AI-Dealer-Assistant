import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import ChatMessage from "./components/ChatMessage";
import ProductGrid from "./components/ProductGrid";
import OrderDraft from "./components/OrderDraft";
import Sidebar from "./components/Sidebar";
import "./styles/App.css";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [orderDraft, setOrderDraft] = useState(null);
  const [draftCount, setDraftCount] = useState(0);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (message) => {
    if (!message.trim()) return;

    // Add user message
    const userMsg = { role: "user", content: message };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await axios.post("/api/chat", { message });
      const data = response.data;

      // Add assistant message
      const assistantMsg = {
        role: "assistant",
        content: data.message,
        products: data.products || [],
        order_summary: data.order_summary,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Update order draft if present
      if (
        data.order_summary &&
        data.order_summary.status === "ready_for_confirmation"
      ) {
        setOrderDraft(data.order_summary);
        setDraftCount((prev) => prev + 1);
      }
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMsg = {
        role: "assistant",
        content:
          "Sorry, there was an error processing your request. Please try again.",
        products: [],
        order_summary: null,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSuggestion = (suggestion) => {
    handleSendMessage(suggestion);
  };

  const handleResetChat = async () => {
    try {
      await axios.post("/api/reset");
      setMessages([]);
      setOrderDraft(null);
      setDraftCount(0);
    } catch (error) {
      console.error("Error resetting chat:", error);
    }
  };

  const handleConfirmOrder = async () => {
    try {
      const response = await axios.post("/api/confirm-order");
      const data = response.data;

      // Add confirmation message
      const confirmMsg = {
        role: "assistant",
        content: data.message,
        products: [],
        order_summary: null,
      };
      setMessages((prev) => [...prev, confirmMsg]);
      setOrderDraft(null);
    } catch (error) {
      console.error("Error confirming order:", error);
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        onSuggestion={handleQuickSuggestion}
        onReset={handleResetChat}
        draftCount={draftCount}
      />

      <div className="main-content">
        <div className="chat-shell">
          <div className="chat-header">
            <div>
              <div className="chat-title">VIKMO Dealer Assistant</div>
              <div className="chat-subtitle">
                Search parts, check stock, and create dealer orders.
              </div>
            </div>
            <div className="status-pill">Live catalogue</div>
          </div>

          <div className="messages-container">
            {messages.length === 0 && (
              <div className="empty-state">
                Ask for a part, vehicle fitment, stock availability, or order
                creation.
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`message-group message-${msg.role}`}>
                <ChatMessage message={msg} />
                {msg.role === "assistant" &&
                  msg.products &&
                  msg.products.length > 0 && (
                    <ProductGrid products={msg.products} />
                  )}
                {msg.role === "assistant" && msg.order_summary && (
                  <OrderDraft
                    order={msg.order_summary}
                    onConfirm={handleConfirmOrder}
                  />
                )}
              </div>
            ))}

            {loading && (
              <div className="message-group message-assistant">
                <div className="chat-message assistant-message">
                  <div className="spinner"></div>
                  <span>Processing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(input);
              }}
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about inventory, stock, or create an order..."
                disabled={loading}
                className="chat-input"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="send-button"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    d="M16.6915026,12.4744748 L3.50612381,13.2599618 C3.19218622,13.2599618 3.03521743,13.4170592 3.03521743,13.5741566 L1.15159189,20.0151496 C0.8376543,20.8006365 0.99,21.89 1.77946707,22.52 C2.41,22.99 3.50612381,23.1 4.13399899,22.8429026 L21.714504,14.0454487 C22.6563168,13.5741566 23.1272231,12.6315722 22.9702544,11.6889879 L4.13399899,1.16513325 C3.34915502,0.9 2.40734225,0.9 1.77946707,1.4429026 C0.994623095,2.0772922 0.837654326,3.16585489 1.15159189,3.95136175 L3.03521743,10.3923548 C3.03521743,10.5494521 3.19218622,10.7065495 3.50612381,10.7065495 L16.6915026,11.4920364 C16.6915026,11.4920364 17.1624089,11.4920364 17.1624089,12.0349409 C17.1624089,12.5778454 16.6915026,12.4744748 16.6915026,12.4744748 Z"
                    fill="currentColor"
                  ></path>
                </svg>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
