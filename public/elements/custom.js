// chainlit_custom.js

class SidebarProgressBar extends HTMLElement {
    constructor() {
      super();
      // Attach a shadow root for encapsulated styling
      this.attachShadow({ mode: "open" });
  
      // Basic HTML & CSS for the progress bar
      this.shadowRoot.innerHTML = `
        <style>
          .container {
            font-family: sans-serif;
            margin: 16px;
            padding: 8px;
            background-color: #2f2f2f;
            border-radius: 6px;
            color: #fff;
          }
          .label {
            margin-bottom: 4px;
            font-size: 14px;
          }
          .progress-container {
            background: #555;
            border-radius: 4px;
            overflow: hidden;
            height: 10px;
          }
          .progress-bar {
            background: #00c853;
            height: 100%;
            width: 0%;
            transition: width 0.5s ease;
          }
        </style>
        <div class="container">
          <div class="label">Progress: <span id="progress-value">0</span>%</div>
          <div class="progress-container">
            <div class="progress-bar" id="progress-bar"></div>
          </div>
        </div>
      `;
    }
  
    connectedCallback() {
      // Called when element is inserted into the DOM
      this.initWebSocket();
    }
  
    initWebSocket() {
      // Update this URL to match your backend's WebSocket endpoint
      const ws = new WebSocket("ws://localhost:8000/ws/progress");
  
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const progress = data.progress || 0;
  
        // Update the bar width
        const bar = this.shadowRoot.getElementById("progress-bar");
        bar.style.width = `${progress}%`;
  
        // Update the text label
        const label = this.shadowRoot.getElementById("progress-value");
        label.textContent = progress;
      };
  
      ws.onclose = () => {
        console.log("WebSocket connection closed");
      };
    }
  }
  
  // Register custom element so we can use <sidebar-progress-bar> in Chainlit
  customElements.define("sidebar-progress-bar", SidebarProgressBar);
  