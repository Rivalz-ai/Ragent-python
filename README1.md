# Multi-Agent Orchestration Demos

This repository contains two demonstration applications showcasing different approaches to multi-agent orchestration using LLMs.

## Demo Applications

### Demo 1: Simple Agent Orchestration (app.py)
This demo demonstrates a basic multi-agent system where user queries are routed to specialized agents:
- **Tech Agent**: Handles technology-related queries including software, hardware, AI, cybersecurity, etc.
- **Travel Agent**: Responds to travel-related inquiries, itineraries, and destination information
- **Health Agent**: Provides information on health, wellness, nutrition, and fitness
- **X Agent**: Specializes in Twitter/X platform interactions

The system uses an OpenAI classifier to intelligently route user queries to the most appropriate agent.

### Demo 2: RX Team Swarm System (main_rx_system.py)
This more advanced demo showcases a swarm architecture with:
- **RX Team Supervisor**: Coordinates a team of X/Twitter agents for social media management
- **Health Agent**: Handles health-related queries
- **Travel Agent**: Manages travel inquiries
- **Default Agent**: Handles general questions when no specialized agent is appropriate

This system demonstrates agent collaboration with a supervisor-led team structure, where the RX supervisor can delegate tasks to appropriate agents within its team while collaborating with external specialized agents.

## Setup Instructions

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)
- An OpenAI API key (store in the `.env` file)
- Make sure you have [`ollama`](https://ollama.com/) installed and running the model specified in `ollamaAgent.py`

### Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   ```

   Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API Keys**
   Create or modify the `.env` file in the project directory:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Running the Demos

#### Demo 1: Basic Orchestration
```bash
chainlit run app.py -w
```

#### Demo 2: RX Team Swarm System
```bash
chainlit run main_rx_system.py -w
```

## Testing the Demos

### Demo 1: Simple Agent Orchestration (app.py)
Sample queries to test different agents:
- "What are the latest advancements in quantum computing?" (Tech Agent)
- "Recommend some places to visit in Tokyo." (Travel Agent)
- "How can I improve my sleep quality?" (Health Agent)
- "Can you help me draft a tweet about AI innovations?" (X Agent)

### Demo 2: RX Team Swarm System (main_rx_system.py)
This demo shows how different agents collaborate under supervision:
- "I'd like to post a series of tweets about my upcoming travel to Barcelona." (Engages RX Team Supervisor)
- "What are some healthy activities I can do while traveling?" (Combines health and travel expertise)
- "Can you suggest some tech conferences happening in Europe this year?" (General knowledge query)

## System Architecture

### Demo 1: Basic Agent Routing
- Uses a direct classification-based routing approach
- Each agent operates independently
- Simple request-response pattern

### Demo 2: Swarm Architecture
- Hierarchical structure with supervisor-agent relationship
- Shared memory between agents for context awareness
- Complex agent coordination through supervisor delegation
- Demonstrates a more realistic enterprise application of multi-agent systems