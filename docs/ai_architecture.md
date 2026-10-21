# AI Copilot Architecture

## 1. Overview

The AI-Powered HR Operations Copilot integrates AI capabilities into the existing CB Nest HRMS. It allows employees, managers, and administrators to interact with HR policies, permitted HR data, and supported HR operations using natural language.

The implementation uses a routing layer to direct requests to the appropriate AI capability.

## 2. High-Level Architecture

```text
User (Employee / Manager / Admin)
                |
                v
        HRMS Frontend
                |
                v
       FastAPI Authentication
                |
                v
       AI Copilot Endpoint
       /api/v1/chat/copilot
                |
                v
         Intent Classifier
                |
       +--------+---------+
       |        |         |
       v        v         v
   Policy RAG  SQL Agent  HR Action Agent
       |        |         |
       v        v         v
 Retrieval   SQL Guardrails  Action Planner
       |        |         |
       v        v         v
 Policy Docs  Row-Level     Action Validator
              Access             |
                 |               v
                 v        Existing HR Services
            SQLite DB            |
                 |               v
                 +--------> HRMS Database

       AI Audit Logging
       (Successful and rejected operations)
```

## 3. Main Components

### 3.1 Authentication and Authorization

The FastAPI backend identifies the authenticated user and their role. AI capabilities are checked against role-based permissions before execution.

### 3.2 Intent Classification and Routing

The Copilot classifies a natural-language request and routes it to one of the supported capabilities:

- **Policy Query:** Answers questions using HR policy documents.
- **Employee Query:** Retrieves permitted HR data through guarded SQL.
- **HR Action:** Processes supported HR actions through existing backend services.

Unknown or unsupported requests receive a safe response.

### 3.3 Policy RAG

The Policy RAG capability retrieves relevant policy content and uses it to generate grounded answers. It should cite supporting sources and avoid inventing rules when the available documents do not contain the answer.

### 3.4 SQL Agent

The SQL Agent generates read-only SQL queries using an approved schema.

Before execution, the backend validates the query and applies server-controlled row-level access restrictions. Only approved tables and columns can be queried.

### 3.5 HR Task Automation Agent

The action planner converts natural-language requests into structured actions. The action validator checks the proposed action before execution.

Supported actions use existing backend services and APIs. The AI agent must not directly modify database records.

### 3.6 Audit Logging

The audit service records relevant AI operations, including the authenticated employee, role, capability, action, status, error code, and timestamp.

Both successful and rejected operations are logged in the tested SQL and HR action flows.

## 4. Security Principles

- Authenticate users before processing protected requests.
- Enforce role-based capability permissions.
- Validate generated SQL before execution.
- Apply server-controlled row-level restrictions.
- Reject unsupported actions and unsafe queries.
- Execute HR mutations through existing backend services.
- Keep an audit trail of successful and rejected operations.
- Ground policy answers in retrieved source documents.

## 5. Current Limitations

- Policy-source relevance and completeness require further evaluation.
- Row-level security and manager-to-employee authorization need additional independent verification.
- Policy RAG audit coverage needs confirmation.
- Frontend and end-to-end validation must be completed before claiming full integration.

