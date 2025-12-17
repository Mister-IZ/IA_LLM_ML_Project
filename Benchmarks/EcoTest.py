import os, sys 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from codecarbon import EmissionsTracker
from testAgent import testAgent
from newAgent import NewAgent
from agent import SocialAgentLangChain




agent = testAgent()

# Use the agent normally - EcoLogits tracks in the background
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

tracker = EmissionsTracker(project_name="BrusselsEventAgent", output_dir=".", on_csv_write="append")
tracker.start()

try: 
    for question in questions:
        print(f"\nQuestion: {question}")
        response = agent.chat(question)
finally:
    tracker.stop()


# agent = SocialAgentLangChain()
# tracker = EmissionsTracker(project_name="BrusselsEventOldAgent", output_dir=".", on_csv_write="append")
# tracker.start()

# try: 
#     for question in questions:
#         print(f"\nQuestion: {question}")
#         response = agent.chat(question)
# finally:
#     tracker.stop()



# Note: With LangChain, EcoLogits tracks automatically but the impacts
# are attached to the underlying API responses, not the agent's response.
# To see the tracking, check the EcoLogits logs or use a callback.