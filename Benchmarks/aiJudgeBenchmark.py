import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from newAgent import NewAgent
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
from mistralai import Mistral

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

class MistralModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str = "mistral-large-latest"):
        self.model_name = model_name
        self.client = client
    
    def load_model(self):
        return self.client
    
    def generate(self, prompt: str) -> str:
        response = self.client.chat.complete(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    
    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)
    
    def get_model_name(self) -> str:
        return self.model_name

# Initialize custom Mistral model for evaluation
mistral_model = MistralModel()

# Initialize agent
agent = NewAgent()

# Define metrics
event_compliance_metric = GEval(
    name="Event Compliance",
    criteria="Event Compliance - Check if: 1) Exactly 5 events of the defined genre, 2) 1 or 2 events of the recommended genre, 3) All unique events, 4) Well structured output",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    model=mistral_model,
)

event_relevance_metric = GEval(
    name="Event Relevance",
    criteria="Event Relevance - Check if: 1) Events are of the right type requested, 2)  Events are realistic and actually exist, 3) 2 last 'Recommended' events are of different genre",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    model=mistral_model,
)

# Define test inputs
test_inputs = [
    {
        "input": "Trouve moi EXACTEMENT 5 evenements de MUSIQUE CLASSIQUE à Bruxelles.",
        "expected": "Return 5 classical music events in Brussels."
    },
    {
        "input": "Donne-moi 5 evenements de ROCK à Bruxelles.",
        "expected": "Return 5 rock music events in Brussels."
    },
    {
        "input": "Je veux 5 films tristes projetés à Bruxelles.",
        "expected": "Return 5 sad movies in Brussels."
    },
    {
        "input": "Trouve moi 5 evenements de basket à Bruxelles.",
        "expected": "Return 5 basketball events in Brussels."
    },
]

# Generate actual outputs by calling the agent
print("🚀 Generating agent responses...")
print("=" * 50)

test_cases = []
for i, test in enumerate(test_inputs, 1):
    print(f"\n[{i}/{len(test_inputs)}] Testing: {test['input'][:50]}...")
    
    # Call the agent to get the actual output (string)
    actual_output = agent.chat(test['input'])
    
    print(f"   ✅ Response received ({len(actual_output)} chars)")
    
    # Create test case with the STRING output
    test_cases.append(LLMTestCase(
        input=test['input'],
        actual_output=actual_output,  # This is now a string!
        expected_output=test['expected']
    ))

print("\n" + "=" * 50)
print("🧪 Running DeepEval evaluation...")
print("=" * 50)

def test_deepeval_suite():
    evaluate(
        test_cases=test_cases,
        metrics=[
            event_compliance_metric,
            event_relevance_metric,
        ]
    )

# Run the tests
test_deepeval_suite()