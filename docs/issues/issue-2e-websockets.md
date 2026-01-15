## Description
Learn WebSockets for real-time communication - essential for streaming chat responses like ChatGPT does.

## 🎓 Learning Objectives
By the end of this issue, you will understand:
- [ ] What WebSockets are and how they differ from HTTP
- [ ] When to use WebSockets vs regular HTTP
- [ ] How to create WebSocket endpoints in FastAPI
- [ ] How to stream data to clients in real-time
- [ ] How to handle WebSocket connections properly

## 📚 Concepts to Learn

### 1. HTTP vs WebSocket

**HTTP (Request-Response):**
```
Client: "Hey server, any updates?"
Server: "Nope"
(1 second later)
Client: "Hey server, any updates?"
Server: "Nope"
(1 second later)
Client: "Hey server, any updates?"
Server: "Yes! Here's the data"

Problem: Client keeps asking (polling) = wasteful
```

**WebSocket (Persistent Connection):**
```
Client: "Let's stay connected"
Server: "OK, connection open"
...
(Server has update)
Server: "Here's new data!" (pushes to client)
...
(Server has another update)
Server: "Here's more data!" (pushes to client)

Better: Server pushes when ready = efficient
```

### 2. Why WebSockets for OSlash?

When you ask a question in chat:
- **Without streaming:** Wait 5 seconds... then see entire response at once
- **With streaming:** See words appear one by one, like ChatGPT

```
Without WebSocket:
User: "Summarize this document"
[Loading... 5 seconds...]
"The document discusses Q4 sales performance..."

With WebSocket:
User: "Summarize this document"
"The" → "document" → "discusses" → "Q4" → "sales" → ...
(Each word appears as it's generated)
```

### 3. WebSocket Lifecycle

```
1. Client connects     → ws://localhost:8000/ws
2. Connection opened   → Server accepts
3. Bidirectional chat  → Client sends, Server sends
4. Connection closed   → Either side disconnects
```

## 🛠️ Hands-On Exercise

### Step 1: Basic WebSocket

Create `server/learn/05_websocket.py`:

```python
"""
WebSocket - Learning Exercise
Run with: uvicorn learn.05_websocket:app --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio

app = FastAPI(title="WebSocket Learning")

# Simple HTML page to test WebSocket
html = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
    <style>
        body { font-family: system-ui; max-width: 600px; margin: 50px auto; }
        #messages { border: 1px solid #ccc; height: 300px; overflow-y: auto; padding: 10px; }
        .message { margin: 5px 0; padding: 5px; background: #f0f0f0; border-radius: 4px; }
        .sent { background: #d4edda; }
        .received { background: #cce5ff; }
        input { width: 70%; padding: 10px; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>WebSocket Test</h1>
    <div id="messages"></div>
    <br>
    <input type="text" id="messageInput" placeholder="Type a message...">
    <button onclick="sendMessage()">Send</button>
    
    <script>
        const ws = new WebSocket("ws://localhost:8000/ws");
        const messages = document.getElementById("messages");
        
        ws.onopen = () => {
            addMessage("Connected to server", "received");
        };
        
        ws.onmessage = (event) => {
            addMessage("Server: " + event.data, "received");
        };
        
        ws.onclose = () => {
            addMessage("Disconnected", "received");
        };
        
        function sendMessage() {
            const input = document.getElementById("messageInput");
            const message = input.value;
            if (message) {
                ws.send(message);
                addMessage("You: " + message, "sent");
                input.value = "";
            }
        }
        
        function addMessage(text, type) {
            const div = document.createElement("div");
            div.className = "message " + type;
            div.textContent = text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }
        
        // Send on Enter key
        document.getElementById("messageInput").addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    """Serve the test page."""
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Basic WebSocket endpoint.
    Echoes back whatever the client sends.
    """
    # Accept the connection
    await websocket.accept()
    print("Client connected")
    
    try:
        while True:
            # Wait for message from client
            data = await websocket.receive_text()
            print(f"Received: {data}")
            
            # Send response back
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        print("Client disconnected")
```

### Step 2: Streaming Chat Response

```python
# Add to the same file

# Simulate streaming like ChatGPT
async def generate_response(question: str):
    """
    Simulate an AI generating a response word by word.
    In real code, this would call OpenAI with streaming.
    """
    response = f"Based on your question about '{question}', I can tell you that this is a simulated streaming response. Each word is sent separately to demonstrate real-time streaming capabilities."
    
    for word in response.split():
        yield word + " "
        await asyncio.sleep(0.1)  # Simulate generation time

@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    Chat WebSocket with streaming responses.
    Like ChatGPT's streaming effect!
    """
    await websocket.accept()
    print("Chat client connected")
    
    try:
        while True:
            # Receive question from client
            question = await websocket.receive_text()
            print(f"Question: {question}")
            
            # Stream the response word by word
            await websocket.send_json({"type": "start"})
            
            async for word in generate_response(question):
                await websocket.send_json({
                    "type": "token",
                    "content": word
                })
            
            await websocket.send_json({"type": "end"})
            
    except WebSocketDisconnect:
        print("Chat client disconnected")

# HTML page for chat
chat_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Streaming Chat</title>
    <style>
        body { font-family: system-ui; max-width: 600px; margin: 50px auto; }
        #chat { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; }
        .user { color: blue; margin: 10px 0; }
        .assistant { color: green; margin: 10px 0; }
        .streaming { opacity: 0.7; }
        input { width: 70%; padding: 10px; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>Streaming Chat Demo</h1>
    <div id="chat"></div>
    <br>
    <input type="text" id="question" placeholder="Ask a question...">
    <button onclick="askQuestion()">Ask</button>
    
    <script>
        const ws = new WebSocket("ws://localhost:8000/ws/chat");
        const chat = document.getElementById("chat");
        let currentResponse = null;
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "start") {
                // Create new response element
                currentResponse = document.createElement("div");
                currentResponse.className = "assistant streaming";
                currentResponse.innerHTML = "<strong>Assistant:</strong> ";
                chat.appendChild(currentResponse);
            } else if (data.type === "token") {
                // Append token to current response
                currentResponse.innerHTML += data.content;
                chat.scrollTop = chat.scrollHeight;
            } else if (data.type === "end") {
                // Mark response as complete
                currentResponse.className = "assistant";
                currentResponse = null;
            }
        };
        
        function askQuestion() {
            const input = document.getElementById("question");
            const question = input.value;
            if (question) {
                // Show user question
                const userDiv = document.createElement("div");
                userDiv.className = "user";
                userDiv.innerHTML = "<strong>You:</strong> " + question;
                chat.appendChild(userDiv);
                
                // Send to server
                ws.send(question);
                input.value = "";
            }
        }
        
        document.getElementById("question").addEventListener("keypress", (e) => {
            if (e.key === "Enter") askQuestion();
        });
    </script>
</body>
</html>
"""

@app.get("/chat")
async def get_chat():
    """Serve the streaming chat page."""
    return HTMLResponse(chat_html)
```

### Step 3: Connection Manager (Multiple Clients)

```python
# Add to the same file

class ConnectionManager:
    """Manage multiple WebSocket connections."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: str):
        """Send message to all connected clients."""
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/broadcast")
async def broadcast_websocket(websocket: WebSocket):
    """
    Broadcast WebSocket - messages go to all clients.
    Open multiple browser tabs to see it work!
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast to everyone
            await manager.broadcast(f"Someone said: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Step 4: Test Everything

```bash
cd server
uvicorn learn.05_websocket:app --reload

# Test basic WebSocket
open http://localhost:8000/

# Test streaming chat (like ChatGPT!)
open http://localhost:8000/chat

# Test broadcast (open multiple tabs)
# Go to http://localhost:8000/ in multiple tabs
# Messages from one tab appear in all tabs!
```

## 🎯 WebSocket in OSlash

This is how chat will work:

```python
@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    try:
        while True:
            # Receive question
            data = await websocket.receive_json()
            question = data["question"]
            
            # Get context from search results
            context = await get_search_context(session_id)
            
            # Stream response from OpenAI
            await websocket.send_json({"type": "start"})
            
            async for chunk in openai_stream(question, context):
                await websocket.send_json({
                    "type": "token",
                    "content": chunk
                })
            
            await websocket.send_json({"type": "end"})
            
    except WebSocketDisconnect:
        pass
```

## ✅ Acceptance Criteria
- [ ] Can explain difference between HTTP and WebSocket
- [ ] Can create a basic WebSocket endpoint
- [ ] Can send and receive messages over WebSocket
- [ ] Can implement streaming responses
- [ ] Can manage multiple WebSocket connections

## 🔗 Resources
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

## ⏱️ Estimated Time
2 hours

## ➡️ Next
After completing this, you're ready to implement Issue #2: Set Up FastAPI Server Skeleton!

