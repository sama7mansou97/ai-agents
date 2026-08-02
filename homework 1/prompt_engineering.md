# Prompt Engineering Concepts & Reflections

In this assignment, we transformed a single-prompt resume assistant into a multi-expert AI agent system. To achieve reliable behavior across specialized tasks (reading data, writing data, content synthesis, and orchestration), we applied three core Prompt Engineering techniques:

---

## 1. Few-Shot Prompting

* **Description:** Few-Shot Prompting involves providing the Language Model with concrete examples of input-output pairs inside the prompt before asking it to solve a new request. Instead of just instructing the model *what* to do, we show it *how* previous identical tasks were formatted and resolved.

* **Application in our System:** We applied Few-Shot Prompting primarily in the `Database Read Expert` and `Database Write Expert` configurations (stored in `llm_roles.csv`). For instance, we provided example pairs showing user queries mapped strictly to raw executable SQL statements or executable Python code without any conversational filler or Markdown wrapping.

* **Effectiveness:** **Extremely High.** Zero-shot attempts often resulted in the LLM adding introductory conversational text (e.g., *"Here is your SQL query:"*) or invalid markdown formatting, which broke the programmatic execution (`exec()` and `sqlite3`). Few-shot prompting successfully constrained the model to strictly output clean, syntax-valid code/queries every time.

---

## 2. Task Decomposition (Multi-Agent Routing)

* **Description:** Task Decomposition is the process of breaking down a complex, multi-step instruction into smaller, manageable sub-tasks that can be solved sequentially or by specialized modules.

* **Application in our System:** We implemented this via the **Orchestrator** agent. When a user submits a compound request (e.g., *"Does he know React? If not, add it to MSU Research"*), a single prompt struggles to perform both condition evaluation and database mutation cleanly. The Orchestrator decomposes this request into a step-by-step execution plan represented as a Python list of individual expert function calls:
  1. First call: `Database Read Expert` to inspect current skills.
  2. Second call: `Database Write Expert` conditional upon the first outcome.

* **Effectiveness:** **High.** Decomposition prevented logic collisions and hallucinated states. By delegating each atomic action to a dedicated specialist, execution accuracy improved significantly for multi-turn and conditional queries.

---

## 3. Ensembling (Multi-Agent Results Aggregation)

* **Description:** Ensembling is a technique where outputs from multiple independent models or specialized prompts are aggregated to produce a unified, highly reliable final output rather than relying on a single model's response.

* **Application in our System:** In our multi-expert architecture, the **Orchestrator** acts as an aggregator/ensembler. For multi-step queries (e.g., verifying if a skill exists using the Read Expert and then appending it via the Write Expert), the Orchestrator collects individual execution outputs from each expert and combines them into one cohesive answer for the user.

* **Effectiveness:** **High.** Aggregating discrete outputs from focused specialists prevented individual logic errors and provided a cleaner, unified user experience compared to expecting a single prompt to handle query generation, execution, and summary simultaneously.