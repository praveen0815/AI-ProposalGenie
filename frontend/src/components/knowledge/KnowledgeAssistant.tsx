import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ErrorState } from "../ui/ErrorState";
import { apiErrorMessage } from "../../lib/apiError";
import { askKnowledge, searchKnowledge } from "../../services/knowledge";
import type { QueryResult, RetrievedChunk } from "../../types/knowledge";

interface KnowledgeAssistantProps {
  companyId: string;
}

export function KnowledgeAssistant({ companyId }: KnowledgeAssistantProps) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<QueryResult | null>(null);
  const [matches, setMatches] = useState<RetrievedChunk[] | null>(null);
  const [mode, setMode] = useState<"search" | "ask" | null>(null);

  async function submit(nextMode: "search" | "ask") {
    const text = question.trim();
    if (!text) {
      setError("Enter a question first.");
      return;
    }
    setLoading(true);
    setError(null);
    setMode(nextMode);
    try {
      if (nextMode === "search") {
        const found = await searchKnowledge(companyId, text);
        setMatches(found.results);
        setAnswer(null);
      } else {
        const response = await askKnowledge(companyId, text);
        setAnswer(response);
        setMatches(response.context);
      }
    } catch (caught) {
      setAnswer(null);
      setMatches(null);
      setError(apiErrorMessage(caught, "The knowledge request failed."));
    } finally {
      setLoading(false);
    }
  }

  const passages = matches ?? [];

  return (
    <Card>
      <h2 className="text-base font-semibold text-white">Company knowledge assistant</h2>
      <p className="mt-2 text-sm leading-6 text-slate-400">
        Search indexed documents, or ask a question. Answers use only retrieved passages from this company.
      </p>
      <form
        className="mt-4 space-y-3"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          void submit("ask");
        }}
      >
        <label className="field-label" htmlFor="knowledge-question">
          Question
        </label>
        <textarea
          id="knowledge-question"
          className="field min-h-24"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What does our support package include?"
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={loading}>
            {loading && mode === "ask" ? "Asking" : "Ask"}
          </Button>
          <Button type="button" variant="secondary" disabled={loading} onClick={() => void submit("search")}>
            {loading && mode === "search" ? "Searching" : "Search"}
          </Button>
        </div>
      </form>

      {error ? (
        <div className="mt-4">
          <ErrorState title="Knowledge request failed" message={error} />
        </div>
      ) : null}

      {answer ? (
        <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <h3 className="text-sm font-semibold text-cyan-100">Answer</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-100">{answer.answer}</p>
          {answer.sources.length > 0 ? (
            <ul className="mt-3 flex flex-wrap gap-2">
              {answer.sources.map((source) => (
                <li key={source.document_id} className="rounded-full bg-cyan-300/10 px-2.5 py-1 text-xs text-cyan-100">
                  {source.filename}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {matches && passages.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No matching passages in this company's documents.</p>
      ) : null}

      {passages.length > 0 ? (
        <div className="mt-5 space-y-3">
          <h3 className="text-sm font-semibold text-white">Retrieved context</h3>
          {passages.map((passage) => (
            <article key={`${passage.document_id}-${passage.chunk_index}`} className="rounded-xl border border-white/10 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span>{passage.source}</span>
                <span>Similarity {passage.score.toFixed(2)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{passage.text}</p>
            </article>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
