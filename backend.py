from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel as V1BaseModel, Field
import json
import re

app = FastAPI(title="Sustainable Travel Planner Backend")

# REPLACE WITH YOUR ACTUAL GEMINI API KEY
# Make sure to replace this with your actual key and consider storing it securely.
GEMINI_API_KEY = ""

try:
    # Use the most widely available model
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-pro",  # This should work globally
        google_api_key=GEMINI_API_KEY,
        temperature=0.7
    )
except Exception as e:
    print(f"Error initializing Gemini: {e}")
    llm = None

class TravelState(V1BaseModel):
    messages: List[Dict[str, str]] = []
    destination: str = ""
    duration: int = 0
    interests: List[str] = []
    sustainability_focus: str = ""
    itinerary: str = ""
    
class ExtractedInfo(V1BaseModel):
    """Extracted travel information from user input."""
    destination: str = Field(description="The destination of the trip.", default=None)
    duration: int = Field(description="The duration of the trip in days.", default=None)
    interests: List[str] = Field(description="A list of interests or activities for the trip.", default=None)
    sustainability_focus: str = Field(description="The primary sustainability focus of the trip.", default=None)

def create_travel_graph():
    if not llm:
        raise RuntimeError("LLM not initialized")
    
    def collect_requirements(state: TravelState):
        current_message = state.messages[-1]["content"] if state.messages else "Start."
        
        # Use LLM with a Pydantic output parser to extract structured data
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract travel details from the user's message. If a value is not present, return None. "
                       "Provide the output as a JSON object with keys: 'destination', 'duration', 'interests', and 'sustainability_focus'. "
                       "interests should be a list of strings, duration should be an integer."),
            ("human", f"{current_message}")
        ])
        
        extraction_chain = extraction_prompt | llm.with_structured_output(ExtractedInfo)
        
        try:
            extracted_data = extraction_chain.invoke({})
            print(f"Extracted data: {extracted_data}") # For debugging
            
            # Update the state with extracted data
            if extracted_data.destination:
                state.destination = extracted_data.destination
            if extracted_data.duration:
                state.duration = extracted_data.duration
            if extracted_data.interests:
                state.interests = extracted_data.interests
            if extracted_data.sustainability_focus:
                state.sustainability_focus = extracted_data.sustainability_focus
            
        except Exception as e:
            print(f"Error during data extraction: {e}")

        # The LLM still needs to respond to the user, so we have a second prompt for the conversational part.
        response_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a sustainable travel assistant. Acknowledge the user's input and politely ask for any missing information (destination, duration, interests, or sustainability priorities)."),
            ("human", f"{current_message}")
        ])
        
        response_chain = response_prompt | llm
        llm_response = response_chain.invoke({})
        
        state.messages.append({"role": "assistant", "content": llm_response.content})
        
        return state

    def generate_itinerary(state: TravelState):
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a sustainable travel planner. Create a detailed, day-by-day sustainable itinerary. "
                       "The trip is for {duration} days in {destination}. The user's interests are: {interests}. "
                       "The primary sustainability focus is: {sustainability_focus}. "
                       "Include specific recommendations for eco-friendly activities, transport, and dining."),
            ("human", "Create itinerary.")
        ])
        
        # Use existing state data for the prompt, providing sensible defaults if not found
        destination = state.destination or "a sustainable destination like Costa Rica"
        duration = state.duration or 5
        interests = ", ".join(state.interests) if state.interests else "eco-tourism and local culture"
        sustainability_focus = state.sustainability_focus or "low carbon footprint"
        
        chain = prompt | llm
        response = chain.invoke({
            "duration": duration,
            "destination": destination,
            "interests": interests,
            "sustainability_focus": sustainability_focus
        })
        state.itinerary = response.content
        state.messages.append({"role": "assistant", "content": response.content})
        return state

    def should_generate_itinerary(state: TravelState) -> str:
        # Check if all required fields are filled.
        if state.destination and state.duration > 0 and state.interests and state.sustainability_focus:
            return "generate"
        
        # As a fallback, use the original condition
        last_message_content = state.messages[-1]["content"].lower()
        if "itinerary" in last_message_content or "plan my trip" in last_message_content:
            return "generate"
            
        return "collect"

    workflow = StateGraph(TravelState)
    workflow.add_node("collect", collect_requirements)
    workflow.add_node("generate", generate_itinerary)
    workflow.set_entry_point("collect")
    workflow.add_conditional_edges("collect", should_generate_itinerary, {"collect": "collect", "generate": "generate"})
    workflow.add_edge("generate", END)
    return workflow.compile()

try:
    travel_graph = create_travel_graph()
except Exception as e:
    travel_graph = None
    print(f"Error creating graph: {e}")

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

conversations = {}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not travel_graph:
        raise HTTPException(status_code=500, detail="Chatbot not initialized")
    
    if request.conversation_id not in conversations:
        conversations[request.conversation_id] = TravelState()
    
    state = conversations[request.conversation_id]
    state.messages.append({"role": "user", "content": request.message})
    
    try:
        # We need to manually invoke with the state as the input since the nodes don't have a single input variable
        result = travel_graph.invoke(state)
        conversations[request.conversation_id] = result
        response = result.messages[-1]["content"]
    except Exception as e:
        response = f"Backend processing error: {str(e)}"
    
    return ChatResponse(response=response, conversation_id=request.conversation_id)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "llm_initialized": llm is not None, 
        "graph_initialized": travel_graph is not None,
        "conversations_count": len(conversations)
    }
