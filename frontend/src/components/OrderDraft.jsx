import React from "react";
import "../styles/OrderDraft.css";

function OrderDraft({ order, onConfirm }) {
  if (!order || order.status !== "ready_for_confirmation") {
    if (order && order.errors && order.errors.length > 0) {
      return (
        <div className="order-error">
          <div className="error-icon">⚠️</div>
          <div className="error-message">{order.errors.join("; ")}</div>
        </div>
      );
    }
    return null;
  }

  const totalAmount = order.total_inr || 0;

  return (
    <div className="order-wrap">
      <div className="order-card">
        <div className="order-header">
          <div className="order-title">Order Draft</div>
          <div className="order-status">DRAFT</div>
        </div>

        <div className="order-section">
          <div className="section-label">DEALER</div>
          <div className="section-value">
            {order.dealer || "Current Dealer"}
          </div>
        </div>

        <div className="order-section">
          <div className="section-label">ITEMS</div>
          <div className="order-items">
            {order.items &&
              order.items.map((item, idx) => (
                <div key={idx} className="order-line">
                  <div className="item-details">
                    <div className="item-quantity">
                      {item.quantity} × {item.name}
                    </div>
                    <div className="item-sku">{item.sku}</div>
                  </div>
                  <div className="item-price">
                    INR {parseInt(item.line_total_inr).toLocaleString("en-IN")}
                  </div>
                </div>
              ))}
          </div>
        </div>

        <div className="order-total">
          <div>Estimated Total</div>
          <div className="total-amount">
            INR {parseInt(totalAmount).toLocaleString("en-IN")}
          </div>
        </div>

        <button className="confirm-button" onClick={onConfirm}>
          Confirm Order
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </button>
      </div>
    </div>
  );
}

export default OrderDraft;
