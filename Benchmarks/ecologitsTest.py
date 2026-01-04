# Environment setup using official mistralai client (no LangChain)
import os, json, inspect, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

# Initialize EcoLogits BEFORE importing/creating Mistral client
from ecologits import EcoLogits
EcoLogits.init(providers=['mistralai'])

from typing import Callable, List
import requests
from datetime import datetime

from mistralai import Mistral, UserMessage, ToolMessage

from toolsFolder.eventBriteTool import get_eventBrite_events_for_llm
from toolsFolder.ticketMasterTool import get_ticketmaster_events_for_llm
from toolsFolder.eventBrusselsTool import get_brussels_events_for_llm

# Import tokenizer - use tiktoken which is compatible with Mistral
TOKENIZER_AVAILABLE = False
tokenizer = None

try:
    import tiktoken
    tokenizer = tiktoken.get_encoding("cl100k_base")
    TOKENIZER_AVAILABLE = True
    print("✅ Tokenizer loaded (tiktoken cl100k_base)")
except ImportError:
    print("⚠️ tiktoken not installed - will estimate tokens (~4 chars/token)")

API_KEY = os.getenv("MISTRAL_API_KEY")
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_CONSUMER_KEY")
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_PRIVATE_TOKEN")
if not API_KEY:
    print("Warning: MISTRAL_API_KEY is not set.")

MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.0"))
client = Mistral(api_key=API_KEY)

print(f"Environment loaded! Using model: {MODEL_NAME}")


# Carbon emissions tracker
class CarbonTracker:
    def __init__(self):
        self.total_energy = 0.0
        self.total_gwp = 0.0
        self.call_count = 0
        self.calls = []
    
    def track(self, response, context=""):
        """Track emissions from a Mistral API response."""
        if hasattr(response, 'impacts') and response.impacts is not None:
            impacts = response.impacts
            self.total_energy += impacts.energy.value
            self.total_gwp += impacts.gwp.value
            self.call_count += 1
            self.calls.append({
                'context': context,
                'energy': impacts.energy.value,
                'gwp': impacts.gwp.value,
                'energy_unit': str(impacts.energy.unit),
                'gwp_unit': str(impacts.gwp.unit)
            })
            print(f"      🌱 CO2: {impacts.gwp.value:.6f} {impacts.gwp.unit} | ⚡ Energy: {impacts.energy.value:.6f} {impacts.energy.unit}")
            return True
        return False
    
    def summary(self):
        print("\n" + "=" * 60)
        print("📈 CARBON EMISSIONS SUMMARY")
        print("=" * 60)
        print(f"Total API calls: {self.call_count}")
        print(f"Total energy: {self.total_energy:.6f} kWh")
        print(f"Total CO2: {self.total_gwp:.6f} kgCO2eq")
        if self.call_count > 0:
            print(f"Avg CO2 per call: {self.total_gwp/self.call_count:.6f} kgCO2eq")


carbon_tracker = CarbonTracker()


def build_tool_spec(func: Callable):
    """Build a tool spec dict from a plain python function."""
    sig = inspect.signature(func)
    props = {}
    required = []
    for name, param in sig.parameters.items():
        ann = param.annotation
        ann_type = "string"
        if ann in (int, float):
            ann_type = "number"
        props[name] = {"type": ann_type}
        if param.default is inspect._empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip()[:800],
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required
            }
        }
    }

def count_tokens(text: str) -> int:
    """Count tokens in text. Uses tiktoken if available, otherwise estimates."""
    if TOKENIZER_AVAILABLE and tokenizer:
        return len(tokenizer.encode(text))
    return len(text) // 4

# Token tracking - GLOBAL dictionary
tool_token_usage = {}

def run_tool_chat(user_content: str, funcs: List[Callable], model: str = MODEL_NAME, temperature: float = TEMPERATURE, track_tokens: bool = False):
    """Send a user message, handle any tool calls, return final answer string."""
    global tool_token_usage
    
    if track_tokens:
        tool_token_usage = {}
    
    messages = [UserMessage(role="user", content=user_content)]
    tool_specs = [build_tool_spec(f) for f in funcs]
    
    # First API call - EcoLogits tracks this
    first = client.chat.complete(model=model, messages=messages, tools=tool_specs, temperature=temperature)
    carbon_tracker.track(first, "Initial tool selection")
    
    msg = first.choices[0].message
    tool_calls = msg.tool_calls or []
    if not tool_calls:
        return msg.content
    messages.append(msg)
    
    for tc in tool_calls:
        args = json.loads(tc.function.arguments)
        fn = next((f for f in funcs if f.__name__ == tc.function.name), None)
        if fn is None:
            result = f"Error: function {tc.function.name} not implemented"
        else:
            try:
                result = fn(**args)
                
                if track_tokens:
                    tokens = count_tokens(str(result))
                    tool_token_usage[tc.function.name] = tokens
                    print(f"📊 {tc.function.name}: {tokens:,} tokens")
                    
            except Exception as e:
                result = f"Error executing {tc.function.name}: {e}".strip()
                
        print(f"Tool {tc.function.name}({args}) -> {str(result)[:160]}")
        messages.append(ToolMessage(role="tool", content=str(result), name=tc.function.name, tool_call_id=tc.id))
    
    # Final API call - EcoLogits tracks this
    final = client.chat.complete(model=model, messages=messages, temperature=temperature)
    carbon_tracker.track(final, "Final response generation")
    
    return final.choices[0].message.content


# Run the test
answer = run_tool_chat(
    "Trouve moi EXACTEMENT 5 evenements musicaux à Bruxelles. Utilise les trois tools (Ticketmaster, Brussels API et EventBrite). " \
    "Assure-toi que les 5 evenements sont différents et que tu retournes UNIQUEMENT 5 EVENEMENTS MAXIMUM. " \
    "Si tu utilises les trois tools, partage les 5 slots equitablement ou selon les meilleurs resultats.", 
    [get_ticketmaster_events_for_llm, get_eventBrite_events_for_llm, get_brussels_events_for_llm],
    track_tokens=True
)

print("\n" + "=" * 60)
print("ANSWER:")
print("=" * 60)
print(answer)

# Print carbon emissions summary
carbon_tracker.summary()


