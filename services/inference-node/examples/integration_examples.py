"""
Example: Integrate N3090 Medical LLM with Teleconsultation App
This file shows how to replace OpenAI with your local medical AI inference system.
"""

import requests
import json
import asyncio
from typing import AsyncIterator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
LLM_BASE_URL = "http://localhost:8000"
DEFAULT_MODEL = "MedicalQA"
DEFAULT_TIMEOUT = 30


class MedicalLLMClient:
    """Drop-in replacement for OpenAI client using N3090 Medical LLM"""
    
    def __init__(self, base_url: str = LLM_BASE_URL):
        self.base_url = base_url
        self.chat_completions_url = f"{base_url}/v1/chat/completions"
        self.health_url = f"{base_url}/health"
    
    def health_check(self) -> bool:
        """Check if LLM server is running"""
        try:
            response = requests.get(self.health_url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def chat(
        self,
        messages: list,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        agent_type: str = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> str:
        """
        Send a chat message and get response (non-streaming)
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (e.g., "MedicalQA", "BioMistral", "Qwen")
            temperature: Creativity level (0.0-1.0)
            max_tokens: Max response length
            agent_type: Optional agent type for routing
            timeout: Request timeout in seconds
        
        Returns:
            Response text from LLM
        """
        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        if agent_type:
            payload["agent_type"] = agent_type
        
        try:
            response = requests.post(
                self.chat_completions_url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data['choices'][0]['message']['content']
        
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: list,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        agent_type: str = None
    ) -> AsyncIterator[str]:
        """
        Send a chat message and stream response (for real-time chat UI)
        
        Args:
            messages: List of message dicts
            model: Model name
            temperature: Creativity level
            max_tokens: Max response length
            agent_type: Optional agent type
        
        Yields:
            Response chunks as they arrive
        """
        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        if agent_type:
            payload["agent_type"] = agent_type
        
        try:
            response = requests.post(
                self.chat_completions_url,
                json=payload,
                stream=True,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'choices' in data and len(data['choices']) > 0:
                                chunk = data['choices'][0]['delta'].get('content', '')
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise


# ============================================================================
# EXAMPLE 1: Basic Chat Integration
# ============================================================================

def example_basic_chat():
    """Simple chat example"""
    client = MedicalLLMClient()
    
    # Check if server is running
    if not client.health_check():
        print("❌ LLM server is not running!")
        print("   Start it with: cd /home/dgs/N3090/services/inference-node")
        print("                 uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return
    
    # Send a message
    messages = [
        {"role": "system", "content": "You are a helpful medical AI assistant."},
        {"role": "user", "content": "What are the common symptoms of diabetes?"}
    ]
    
    print("\n📋 Example 1: Basic Chat")
    print("=" * 60)
    print(f"User: {messages[1]['content']}\n")
    
    response = client.chat(messages)
    print(f"Assistant: {response}\n")


# ============================================================================
# EXAMPLE 2: Telemedicine Consultation Chat
# ============================================================================

def example_telemedicine_chat():
    """Simulated telemedicine consultation"""
    client = MedicalLLMClient()
    
    print("\n🏥 Example 2: Telemedicine Consultation")
    print("=" * 60)
    
    # Multi-turn conversation
    messages = [
        {"role": "system", "content": "You are a helpful medical AI assistant supporting telemedicine consultations. Provide clear, professional medical information."},
    ]
    
    user_inputs = [
        "I've been experiencing chest pain for 3 days. Should I be concerned?",
        "It's a dull ache on the left side. I also feel slightly short of breath.",
        "I'm 52 years old and have high cholesterol. What could be causing this?"
    ]
    
    for user_input in user_inputs:
        messages.append({"role": "user", "content": user_input})
        print(f"\nPatient: {user_input}")
        
        # Use MedicalQA for medical expertise
        response = client.chat(messages, model="BioMistral", max_tokens=300)
        messages.append({"role": "assistant", "content": response})
        
        print(f"Doctor AI: {response}")


# ============================================================================
# EXAMPLE 3: Real-time Streaming Chat (for UI)
# ============================================================================

async def example_streaming_chat():
    """Real-time streaming for chat UI"""
    client = MedicalLLMClient()
    
    print("\n⚡ Example 3: Real-time Streaming Chat")
    print("=" * 60)
    
    messages = [
        {"role": "system", "content": "You are a medical expert."},
        {"role": "user", "content": "Explain the pathophysiology of myocardial infarction."}
    ]
    
    print(f"User: {messages[1]['content']}\n")
    print("Assistant: ", end="", flush=True)
    
    async for chunk in client.chat_stream(messages, model="BioMistral"):
        print(chunk, end="", flush=True)
    
    print("\n")


# ============================================================================
# EXAMPLE 4: Insurance/Claims Routing
# ============================================================================

def example_insurance_routing():
    """Route to specialized insurance agent"""
    client = MedicalLLMClient()
    
    print("\n💰 Example 4: Insurance Claims Routing")
    print("=" * 60)
    
    messages = [
        {"role": "system", "content": "You are an insurance claims specialist."},
        {"role": "user", "content": "Will my insurance cover physical therapy for knee surgery?"}
    ]
    
    print(f"User: {messages[1]['content']}\n")
    
    # Route to Claims agent for specialized response
    response = client.chat(
        messages,
        agent_type="Claims",
        model="OpenInsurance",
        max_tokens=400
    )
    
    print(f"Claims Agent: {response}\n")


# ============================================================================
# EXAMPLE 5: Multi-model Fallback
# ============================================================================

def example_model_selection():
    """Select best model based on use case"""
    client = MedicalLLMClient()
    
    print("\n🎯 Example 5: Model Selection")
    print("=" * 60)
    
    use_cases = {
        "Fast Response (Real-time)": "Qwen",
        "Medical Quality": "BioMistral",
        "Balanced": "BiMediX2",
        "Insurance": "OpenInsurance"
    }
    
    message = {"role": "user", "content": "What are common blood pressure values?"}
    
    for use_case, model in use_cases.items():
        response = client.chat(
            [{"role": "system", "content": "You are a helpful medical assistant."},
             message],
            model=model,
            max_tokens=150
        )
        
        print(f"\n{use_case} ({model}):")
        print(f"Response: {response[:150]}...")


# ============================================================================
# EXAMPLE 6: Flask Web App Integration
# ============================================================================

def example_flask_integration():
    """Sample Flask app integration"""
    code = '''
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import requests

app = Flask(__name__)
CORS(app)

LLM_API = "http://localhost:8000/v1/chat/completions"

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint for your telemedicine app"""
    data = request.json
    
    # Prepare LLM request
    llm_payload = {
        "messages": data['messages'],
        "model": data.get('model', 'MedicalQA'),
        "temperature": data.get('temperature', 0.7),
        "max_tokens": data.get('max_tokens', 500),
        "stream": data.get('stream', False)
    }
    
    try:
        response = requests.post(LLM_API, json=llm_payload, timeout=30)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Streaming endpoint for real-time responses"""
    data = request.json
    
    llm_payload = {
        "messages": data['messages'],
        "model": data.get('model', 'MedicalQA'),
        "stream": True,
        "max_tokens": data.get('max_tokens', 500)
    }
    
    def generate():
        response = requests.post(LLM_API, json=llm_payload, stream=True)
        for line in response.iter_lines():
            if line:
                yield line.decode('utf-8') + '\\n'
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
'''
    
    print("\n🌐 Example 6: Flask Web App Integration")
    print("=" * 60)
    print(code)


# ============================================================================
# EXAMPLE 7: React/JavaScript Integration
# ============================================================================

def example_react_integration():
    """Sample React component"""
    code = '''
import React, { useState } from 'react';

function MedicalChat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);

    const sendMessage = async () => {
        if (!input.trim()) return;

        // Add user message
        const newMessages = [
            ...messages,
            { role: 'user', content: input }
        ];
        setMessages(newMessages);
        setInput('');
        setLoading(true);

        try {
            // Call your backend API (which calls N3090)
            const response = await fetch('http://localhost:5000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: newMessages,
                    model: 'BioMistral',
                    stream: false
                })
            });

            const data = await response.json();
            const assistantMessage = data.choices[0].message.content;

            setMessages([
                ...newMessages,
                { role: 'assistant', content: assistantMessage }
            ]);
        } catch (error) {
            console.error('Error:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="chat-container">
            <div className="messages">
                {messages.map((msg, i) => (
                    <div key={i} className={`message ${msg.role}`}>
                        {msg.content}
                    </div>
                ))}
            </div>
            <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask a medical question..."
                disabled={loading}
            />
            <button onClick={sendMessage} disabled={loading}>
                {loading ? 'Loading...' : 'Send'}
            </button>
        </div>
    );
}

export default MedicalChat;
'''
    
    print("\n⚛️  Example 7: React Integration")
    print("=" * 60)
    print(code)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("N3090 Medical LLM Integration Examples")
    print("=" * 60)
    
    # Run examples
    example_basic_chat()
    example_telemedicine_chat()
    example_insurance_routing()
    example_model_selection()
    
    # Show code examples
    print("\n" + "=" * 60)
    example_flask_integration()
    print("\n" + "=" * 60)
    example_react_integration()
    
    # Async example
    print("\n⚡ Running async streaming example...\n")
    asyncio.run(example_streaming_chat())
    
    print("=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)
