
"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  copilot,
  fetchProfile,
  CopilotChatResponse,
  CopilotHistoryMessage,
} from "@/lib/api";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

type Message = {
  role: "user" | "assistant";
  content: string;
  intent?: CopilotChatResponse["intent"];
  sources?: string[];
};

function getErrorMessage(body: unknown, status: number): string {
  if (typeof body !== "object" || body === null) {
    return `Request failed (${status}).`;
  }

  if ("detail" in body) {
    const detail = body.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (
      typeof detail === "object" &&
      detail !== null &&
      "error" in detail
    ) {
      const error = detail.error;

      if (
        typeof error === "object" &&
        error !== null &&
        "message" in error &&
        typeof error.message === "string"
      ) {
        return error.message;
      }
    }
  }

  return `Request failed (${status}).`;
}

function getIntentLabel(intent: CopilotChatResponse["intent"]): string {
  switch (intent) {
    case "POLICY_QUERY":
      return "[POLICY]";
    case "EMPLOYEE_QUERY":
      return "[HR DATA]";
    case "HR_ACTION":
      return "[HR ACTION]";
    default:
      return "[COPILOT]";
  }
}

export default function AICopilotPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [userRole, setUserRole] = useState("EMPLOYEE");

  useEffect(() => {
    const loadUserRole = async () => {
      const token = localStorage.getItem("hrms_access_token");
      if (!token) return;

      try {
        const response = await fetchProfile(token);

        if (
          response.ok &&
          "success" in response.body &&
          response.body.success
        ) {
          setUserRole(
            response.body.data.role?.toUpperCase() || "EMPLOYEE"
          );
        }
      } catch (error) {
        console.error("Unable to load user role:", error);
      }
    };

    loadUserRole();
  }, []);

  const suggestionsByRole: Record<string, string[]> = {
    EMPLOYEE: [
      "What is my remaining leave balance?",
      "How many sick leave days am I allowed?",
      "Show my current project",
      "Create an HR support ticket for a laptop issue.",
      "Apply a sick leave for tomorrow due to health issue.",
    ],
    MANAGER: [
      "Show my team's pending leave requests.",
      "Approve the pending leave request.",
      "Show my team's leave information.",
      "Show tickets assigned to my team.",
      "Apply a sick leave for tomorrow due to health issue.",
    ],
    ADMIN: [
      "Show the current projects.",
      "Show project assignments.",
      "Show all open tickets",
      "Summarize the available HR policies.",
      "Apply a sick leave for tomorrow due to health issue.",
    ],
  };

  const suggestions =
    suggestionsByRole[userRole] ?? suggestionsByRole.EMPLOYEE;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    const token = localStorage.getItem("hrms_access_token");

    if (!token) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: "Please log in before using the AI Copilot.",
        },
      ]);
      return;
    }

    setQuestion("");

    const history: CopilotHistoryMessage[] = messages
      .slice(-6)
      .map(({ role, content }) => ({ role, content }));

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        content: trimmedQuestion,
      },
    ]);

    setLoading(true);

    try {
      const result = await copilot(token, trimmedQuestion, history);

      if (!result.ok) {
        throw new Error(getErrorMessage(result.body, result.status));
      }

      const data = result.body as CopilotChatResponse;
      let content = data.answer || "";

      if (
        data.intent === "HR_ACTION" &&
        data.action === "APPLY_LEAVE" &&
        data.result
      ) {
        const leave = data.result;

        content = [
          data.answer ||
            "Your leave request has been submitted successfully.",
          "",
          `Leave type: ${String(leave.leave_type ?? "-")}`,
          `Start date: ${String(leave.start_date ?? "-")}`,
          `End date: ${String(leave.end_date ?? "-")}`,
          `Status: ${String(leave.status ?? "-")}`,
        ].join("\n");
      } else if (
        data.intent === "HR_ACTION" &&
        typeof data.action === "object" &&
        data.action.action === "CLARIFICATION_REQUIRED"
      ) {
        const missing = data.action.missing ?? [];

        content =
          missing.length > 0
            ? `I need some additional information before I can submit this request.\n\nPlease provide: ${missing.join(", ")}.`
            : "I need some additional information before I can submit this request.";
      } else if (
        data.intent === "HR_ACTION" &&
        typeof data.action === "object" &&
        data.action.action === "UNSUPPORTED_ACTION"
      ) {
        content = "This HR action is not currently supported by the Copilot.";
      } else if (!content) {
        content = "I couldn't generate a response for this request.";
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content,
          intent: data.intent,
          sources: data.sources,
        },
      ]);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Unable to contact the AI service.";

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: errorMessage,
          intent: "HR_ACTION",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen bg-[#0b1020]">
      <Sidebar />

      <section className="flex min-w-0 flex-1 flex-col bg-[#f1f6fd]">
        <Topbar name="User" title="AI Copilot" />

        <div className="flex-1 p-4 md:p-6">
          <main className="mx-auto flex min-h-[80vh] w-full max-w-4xl flex-col gap-6 p-6">
            <header>
              <h1 className="text-3xl font-semibold">AI HR Copilot</h1>

              <p className="mt-2 text-sm text-gray-500">
                Ask about HR policies, permitted HR data, or supported HR
                actions using natural language.
              </p>
            </header>

            <section
              aria-live="polite"
              className="flex-1 space-y-4 rounded-xl border bg-white p-4"
            >
              {messages.length === 0 && (
                <div className="py-8 text-center">
                  <h2 className="text-lg font-medium">
                    How can I help you?
                  </h2>

                  <p className="mt-2 text-sm text-gray-500">
                    Choose a suggested question or ask about HR policies,
                    permitted HR data, or supported HR actions.
                  </p>
                </div>
              )}

              {messages.map((message, index) => (
                <article
                  key={`${index}-${message.role}`}
                  className={`rounded-lg p-4 ${
                    message.role === "user"
                      ? "ml-auto max-w-[85%] bg-blue-50"
                      : "mr-auto max-w-[95%] bg-gray-50"
                  }`}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      {message.role === "user" ? "You" : "AI Copilot"}
                    </p>

                    {message.role === "assistant" && message.intent && (
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-blue-700">
                        {getIntentLabel(message.intent)}
                      </span>
                    )}
                  </div>

                  <p className="whitespace-pre-wrap text-sm leading-6">
                    {message.content}
                  </p>

                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-4 border-t pt-3">
                      <p className="mb-2 text-xs font-semibold">Sources</p>

                      <ul className="list-inside list-disc text-xs text-gray-600">
                        {message.sources.map((source, sourceIndex) => (
                          <li key={`${source}-${sourceIndex}`}>
                            {source}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}

              {loading && (
                <p className="text-sm text-gray-500">
                  AI Copilot is processing your request...
                </p>
              )}

              {/* Separate quick-question section */}
              <div
                className={`border-t pt-4 ${
                  messages.length === 0 ? "mt-2" : "mt-4"
                }`}
              >
                <p className="mb-3 text-xs font-medium text-gray-500">
                  {messages.length === 0
                    ? "Suggested questions for you"
                    : "Quick questions"}
                </p>

                <div className="flex flex-wrap gap-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      disabled={loading}
                      onClick={() => setQuestion(suggestion)}
                      className="rounded-full border border-blue-200 bg-blue-50 px-3 py-2 text-left text-xs text-blue-800 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask anything about HR..."
                maxLength={4000}
                disabled={loading}
                aria-label="AI Copilot question"
                className="min-w-0 flex-1 rounded-lg border bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
              />

              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Thinking..." : "Ask"}
              </button>
            </form>
          </main>
        </div>
      </section>
    </main>
  );
}
