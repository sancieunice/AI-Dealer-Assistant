import React from "react";
import "../styles/Sidebar.css";

function Sidebar({ onSuggestion, onReset, draftCount }) {
  const suggestions = [
    "Need brake pads",
    "For Bajaj Pulsar 150",
    "Check stock for BRK-1042",
    "Order 10 brake pads for Bajaj Pulsar 150 for ABC Motors",
    "Show parts for Yamaha FZ",
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-content">
        <div className="vikmo-logo">
          <div className="logo-mark">V</div>
          <div className="logo-copy">
            <strong>VIKMO</strong>
            <span>Dealer Assistant</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Suggestions</div>
          <div className="suggestions-list">
            {suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                className="suggestion-button"
                onClick={() => onSuggestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-section">
          <div className="sidebar-label">Session</div>
          {draftCount > 0 && (
            <div className="draft-info">
              <span className="draft-badge">{draftCount}</span>
              <span>Draft{draftCount !== 1 ? "s" : ""}</span>
            </div>
          )}
          <button className="reset-button" onClick={onReset}>
            Reset Chat
          </button>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
