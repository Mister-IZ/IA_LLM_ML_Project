import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langchain_community.callbacks import get_openai_callback
from langchain_core.callbacks import BaseCallbackHandler
from newAgent import NewAgent

# Custom callback to track Mistral tokens
class TokenCounterCallback(BaseCallbackHandler):
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.call_count = 0
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes generating."""
        self.call_count += 1
        
        # Try to get token usage from response
        if hasattr(response, 'llm_output') and response.llm_output:
            usage = response.llm_output.get('token_usage', {})
            self.prompt_tokens += usage.get('prompt_tokens', 0)
            self.completion_tokens += usage.get('completion_tokens', 0)
            self.total_tokens += usage.get('total_tokens', 0)
        
        # For Mistral via LangChain, check generations
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, 'generation_info') and gen.generation_info:
                    usage = gen.generation_info.get('usage', {})
                    if usage:
                        self.prompt_tokens += usage.get('prompt_tokens', 0)
                        self.completion_tokens += usage.get('completion_tokens', 0)
                        self.total_tokens += usage.get('total_tokens', 0)
    
    def reset(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.call_count = 0
    
    def print_stats(self):
        print(f"\n📊 TOKEN USAGE STATISTICS:")
        print(f"   🔢 LLM Calls: {self.call_count}")
        print(f"   📥 Prompt tokens: {self.prompt_tokens}")
        print(f"   📤 Completion tokens: {self.completion_tokens}")
        print(f"   📊 Total tokens: {self.total_tokens}")


# Questions to test
questions = [
    "Peux-tu me recommander un événement sportif à Bruxelles ?",
    "Quels sont les meilleurs événements artistiques ce week-end ?",
    "Y a-t-il des concerts de musique live en ville cette semaine ?",
    "Je veux aller au cinéma, quels films sont à l'affiche ?",
    "Quelles activités nature puis-je faire près de Bruxelles ?",
    "Organise-moi une sortie culturelle intéressante.",
    "Quels événements familiaux sont prévus ce mois-ci ?",
    "As-tu des suggestions pour une journée détente en plein air ?",
    "Je veux faire quelquechose avec mes enfants, des idées?",
    "Je veux aller au musée, qu'est-ce qui est recommandé ?"
]


# Create callback and agent
token_counter = TokenCounterCallback()
agent = NewAgent()

# Add callback to the LLM
agent.llm.callbacks = [token_counter]

print("🚀 Starting Token Benchmark...")
print("=" * 50)

results = []

for i, question in enumerate(questions, 1):
    print(f"\n[{i}/{len(questions)}] {question[:50]}...")
    
    # Reset counter for per-question tracking
    tokens_before = token_counter.total_tokens
    
    try:
        response = agent.chat(question)
        tokens_used = token_counter.total_tokens - tokens_before
        results.append({
            "question": question[:40],
            "tokens": tokens_used,
            "response_len": len(response)
        })
        print(f"   ✅ Tokens used: {tokens_used}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 50)
token_counter.print_stats()

print("\n📋 PER-QUESTION BREAKDOWN:")
for r in results:
    print(f"   • {r['question']}... → {r['tokens']} tokens")

# Estimate cost (Mistral Small: ~$0.001/1K tokens)
cost_per_1k = 0.001
estimated_cost = (token_counter.total_tokens / 1000) * cost_per_1k
print(f"\n💰 Estimated cost: ${estimated_cost:.4f}")

#Resultats: 
# Sur 10 questions on a un total de : 30 API calls
# Total tokens: 115493
#Prompt tokens: 109642
#Completion tokens: 5851