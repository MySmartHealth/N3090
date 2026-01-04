"""
Quick Integration Template for Your Teleconsultation App
Replace OpenAI with N3090 Medical LLM in 3 steps
"""

import requests
import json

# ============================================================================
# STEP 1: Replace OpenAI with N3090
# ============================================================================

# BEFORE (OpenAI):
# --------
# from openai import OpenAI
# client = OpenAI(api_key="sk-...")
# response = client.chat.completions.create(
#     model="gpt-3.5-turbo",
#     messages=[...]
# )

# AFTER (N3090):
# --------

def call_medical_llm(messages, model="MedicalQA", stream=False):
    """
    Drop-in replacement for OpenAI API calls
    
    Args:
        messages: List of {"role": "...", "content": "..."} dicts
        model: "Qwen", "BioMistral", "BiMediX2", "OpenInsurance", etc.
        stream: True for streaming, False for complete response
    
    Returns:
        If stream=False: Complete response text
        If stream=True: Generator yielding response chunks
    """
    
    url = "http://localhost:8000/v1/chat/completions"
    
    payload = {
        "messages": messages,
        "model": model,
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": stream
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        if not stream:
            # Return complete response
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            # Return streaming generator
            def stream_response():
                for line in response.iter_lines():
                    if line:
                        text = line.decode('utf-8')
                        if text.startswith('data: '):
                            try:
                                chunk_data = json.loads(text[6:])
                                if 'choices' in chunk_data:
                                    content = chunk_data['choices'][0]['delta'].get('content', '')
                                    if content:
                                        yield content
                            except:
                                pass
            return stream_response()
    
    except Exception as e:
        raise Exception(f"LLM API error: {e}")


# ============================================================================
# STEP 2: Use in Your Telemedicine Chat
# ============================================================================

def telemedicine_chat(user_message, conversation_history=None):
    """
    Handle user message in your telemedicine app
    
    Usage in your chat endpoint:
        response_text = telemedicine_chat("I have a headache")
    """
    
    if conversation_history is None:
        conversation_history = []
    
    # Build message list with context
    messages = [
        {
            "role": "system",
            "content": "You are a helpful medical AI assistant. Provide accurate medical information while reminding users to consult with healthcare professionals for serious conditions."
        }
    ]
    
    # Add conversation history
    messages.extend(conversation_history)
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # Get response from medical LLM
    response = call_medical_llm(messages)
    
    return response


def telemedicine_chat_streaming(user_message, conversation_history=None):
    """
    Streaming version for real-time chat UI
    
    Usage:
        for chunk in telemedicine_chat_streaming("I have a fever"):
            print(chunk, end='', flush=True)
    """
    
    if conversation_history is None:
        conversation_history = []
    
    messages = [
        {
            "role": "system",
            "content": "You are a helpful medical AI assistant. Provide accurate medical information while reminding users to consult with healthcare professionals."
        }
    ]
    
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    # Get streaming response
    return call_medical_llm(messages, stream=True)


# ============================================================================
# STEP 3: Integrate with Your Web Framework
# ============================================================================

# Example for FastAPI:
# --------------------

try:
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import StreamingResponse
    import asyncio
    
    app = FastAPI()
    
    @app.post("/api/chat")
    async def chat_endpoint(message: str):
        """Non-streaming chat endpoint"""
        response = telemedicine_chat(message)
        return {"response": response}
    
    
    @app.websocket("/ws/chat")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time streaming chat"""
        await websocket.accept()
        
        try:
            while True:
                # Receive message from client
                user_message = await websocket.receive_text()
                
                # Get streaming response
                response_generator = telemedicine_chat_streaming(user_message)
                
                # Send chunks back to client
                for chunk in response_generator:
                    await websocket.send_text(chunk)
                
                # Send completion signal
                await websocket.send_text("[DONE]")
        
        except Exception as e:
            await websocket.send_text(f"Error: {e}")
        finally:
            await websocket.close()
    
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# Example for Flask:
# ------------------

try:
    from flask import Flask, request, jsonify, Response
    
    app_flask = Flask(__name__)
    
    @app_flask.route('/api/chat', methods=['POST'])
    def flask_chat():
        """Flask chat endpoint"""
        data = request.json
        user_message = data.get('message', '')
        conversation = data.get('history', [])
        
        response = telemedicine_chat(user_message, conversation)
        return jsonify({"response": response})
    
    
    @app_flask.route('/api/chat/stream', methods=['POST'])
    def flask_chat_stream():
        """Flask streaming endpoint"""
        data = request.json
        user_message = data.get('message', '')
        conversation = data.get('history', [])
        
        def generate():
            for chunk in telemedicine_chat_streaming(user_message, conversation):
                yield chunk
        
        return Response(generate(), mimetype='text/plain')
    
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# ============================================================================
# STEP 4 (Optional): Advanced Features
# ============================================================================

def medical_chat_with_rag(user_message, document_context=None):
    """
    Chat with optional document/knowledge base context
    RAG (Retrieval-Augmented Generation) is automatic for MedicalQA
    """
    
    system_prompt = "You are a medical expert."
    
    # If you have custom knowledge base docs, add them as context
    if document_context:
        system_prompt += f"\n\nRelevant information:\n{document_context}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    response = call_medical_llm(messages, model="MedicalQA")
    return response


def insurance_claims_chat(user_message):
    """
    Specialized insurance/claims assistant
    """
    messages = [
        {"role": "system", "content": "You are an insurance claims specialist."},
        {"role": "user", "content": user_message}
    ]
    
    # Use specialized model for claims
    response = call_medical_llm(messages, model="OpenInsurance")
    return response


def fast_response_chat(user_message):
    """
    Ultra-fast response for real-time chat
    """
    messages = [
        {"role": "system", "content": "You are a helpful medical assistant."},
        {"role": "user", "content": user_message}
    ]
    
    # Use fastest model
    response = call_medical_llm(messages, model="Qwen", max_tokens=200)
    return response


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("Testing N3090 Integration...\n")
    
    # Test 1: Basic chat
    print("1️⃣  Basic Chat Test")
    try:
        response = telemedicine_chat("What is hypertension?")
        print(f"Response: {response[:200]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 2: Multi-turn conversation
    print("2️⃣  Multi-turn Conversation")
    history = [
        {"role": "user", "content": "I have high blood pressure"},
        {"role": "assistant", "content": "High blood pressure requires monitoring..."}
    ]
    try:
        response = telemedicine_chat("What lifestyle changes help?", history)
        print(f"Response: {response[:200]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 3: Streaming (first few chunks)
    print("3️⃣  Streaming Response")
    try:
        chunks = list(telemedicine_chat_streaming("What is diabetes?"))
        streamed_text = ''.join(chunks)
        print(f"Streamed Response: {streamed_text[:200]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 4: Insurance chat
    print("4️⃣  Insurance Claims Chat")
    try:
        response = insurance_claims_chat("Does my insurance cover physical therapy?")
        print(f"Response: {response[:200]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    print("✅ Integration template ready to use!")
    print("\n📚 Next steps:")
    print("   1. Copy this file to your project")
    print("   2. Import and use call_medical_llm() or telemedicine_chat()")
    print("   3. Start N3090: uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("   4. Replace your OpenAI calls with these functions")
