# Browser agent

This is a browser use agent that can take user query in natural language and do actions on behlaf of the user.

## Stack

-   backend: python3, flask
-   frontend: nextjs
-   llm agents: gpt-4o-mini (action plan generator), gpt-4o (vision model, decide browser action)

## Architecture

-   We will use a vision model
-   In a web-page a user can do following actions - `input`, `click` or `extract data`

-   First, we generate an action plan

```json
{
	"user_query": "download invoice of my last amazon order",
	"goto": "https://www.amazon.com",
	"action_plan": [
		"Click on 'Sign In' at the top right corner.",
		"Enter your email/phone number and password, then click 'Sign In'.",
		"Click on 'Returns & Orders' at the top right to view your order history.",
		"Locate the topmost order in the list (this is typically your most recent order).",
		"Click on 'Invoice' or 'Order Details' next to the order.",
		"If you clicked 'Order Details', then click on 'Invoice' or 'View/Print Invoice' on the next page.",
		"When the invoice opens as a PDF, click the download icon or right-click and select 'Download'.",
		"Choose a save location and confirm the download."
	],
	"steps_done": [],
	"goal": "Confirm that a PDF file of the invoice is downloaded and opens correctly showing the order details."
}
```

-   Using playwright we navigate to the goto url
-   When he page loads, we draw bounding boxes with numbers and then take a screenshot of it
-   We send the screenshot and action plan to the LLM
-   LLM decides the action

```json
{
	"box_click": 1,
	"input_text": "system generated",
	"extracted_data": ""
}
```

-   Action is executed by the program
-   program updates steps_done
-   Loop continues until all steps are done
-   Outside of the loop goal is checked for validation
-   If goal not achieved then restart the loop from the last step

## How to run it

### backend

```shell
cd backend/
python3 -m venv .venv
source .venv/bin/activate
python app.py
```

### frontend

```shell
cd frontend/
npm i
npm run dev
```

## Future extendability

-   **Support parallel browser use queries** - We can use temporal workers to parallelize query processing.
    For notfying user on the progress `sse.publish` supports `channel=query-id`,

## Resiliency

-   **Handle processor crash** - We can delegate the processing workloads to temporal workers, temporal handles
    checkpointing and resumability.

-   **Handle unresponsive pages/browser crash** - We can implement timeout in the workers along in combination with
    a delayed queue using SQS for picking up the same job after some cooldown period.

## Optimisations

-   **Reduce hallucinations** -

-   **Security**

-   **Tracing, caching & feedback** - Currently in this project there is no tracing thus we cannot record feedback & score the output
    Prompt caching is required to control cost
    We can use langfuse to implement these in future

-   **User perceived latency** -
    Currently in this project we are not using streaming from models
    We can stream from models and stream the response to frontend usig SSE (server-sent-event) in future so the response delay from the chatbot seems less
# cd-browser-agent
