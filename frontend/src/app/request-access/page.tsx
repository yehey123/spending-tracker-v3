"use client";

import { useState } from "react";

export default function RequestAccessPage() {
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("submitting");
    setMessage("");

    try {
      const baseUrl =
        process.env.NEXT_PUBLIC_API_URL ||
        (typeof window !== "undefined"
          ? localStorage.getItem("spending_tracker_backend_url") ?? ""
          : "") ||
        "/api";

      const res = await fetch(`${baseUrl}/request-access`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, reason: reason || undefined }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail ?? `Error ${res.status}`);
      }

      const data = await res.json();
      setStatus("success");
      setMessage(data.message ?? "Request submitted successfully.");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "An unexpected error occurred.");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow p-8">
        <h1 className="text-2xl font-bold mb-2 text-gray-900 dark:text-gray-100">
          Request Access
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mb-6 text-sm">
          Submit your email address. The owner will review your request and send
          you an invite link if approved.
        </p>

        {status === "success" ? (
          <div className="rounded-lg bg-green-50 dark:bg-green-900/30 p-4 text-green-800 dark:text-green-200 text-sm">
            {message}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Email address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="reason"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Reason{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Why do you want access?"
              />
            </div>

            {status === "error" && (
              <p className="text-red-600 dark:text-red-400 text-sm">{message}</p>
            )}

            <button
              type="submit"
              disabled={status === "submitting"}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 text-sm transition-colors"
            >
              {status === "submitting" ? "Submitting…" : "Request Access"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
