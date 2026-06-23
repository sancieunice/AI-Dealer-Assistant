# VIKMO Dealer Assistant - Frontend

A modern React-based frontend for the VIKMO Dealer Assistant application.

## Setup

### Prerequisites

- Node.js 16+ and npm

### Installation

1. Install dependencies:

```bash
npm install
```

2. Start the development server:

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

## Architecture

- **React 18** - UI framework
- **Axios** - HTTP client for API communication
- **Vite** - Fast build tool and dev server
- **CSS3** - Custom styling with CSS variables

## Project Structure

```
src/
├── components/          # React components
│   ├── ChatMessage.jsx
│   ├── ProductGrid.jsx
│   ├── OrderDraft.jsx
│   └── Sidebar.jsx
├── styles/             # CSS files
│   ├── global.css      # Global styles and variables
│   ├── App.css         # App layout styles
│   ├── ChatMessage.css
│   ├── ProductGrid.css
│   ├── OrderDraft.css
│   └── Sidebar.css
├── App.jsx             # Main app component
└── main.jsx            # Entry point
```

## Features

- Real-time chat interface
- Product search and display
- Stock availability checking
- Order creation and draft management
- Responsive design
- Clean, intuitive UI

## API Communication

The frontend communicates with a Flask backend at `http://localhost:5000`.

### API Endpoints

- `POST /api/chat` - Send chat message
- `POST /api/reset` - Reset conversation
- `POST /api/confirm-order` - Confirm order draft
- `GET /api/messages` - Get all messages
- `GET /api/order-draft` - Get current order draft
- `GET /api/health` - Health check

## Development

The dev server includes a proxy for API calls, so requests to `/api/*` are automatically forwarded to the backend.

To customize the backend URL, modify the proxy settings in `vite.config.js`.
