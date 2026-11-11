import { useState, useRef, useEffect } from "react";
import { Trash2, Bot, Settings, Cpu } from "lucide-react";
import { useNavigate } from "react-router-dom";
import ChatMessage from "../components/chat/ChatMessage";
import ChatInput from "../components/chat/ChatInput";
import { useSession } from "../hooks/useSession";
import { useAuth } from "../hooks/useAuth";
import { sendChat } from "../services/api";
import toast from "react-hot-toast";

const WELCOME = {
  role: "assistant",
  content:
    "Hi! I'm **InsightAgent AI** — your research assistant.\n\n" +
    "I can:\n" +
    "- 🔍 Search the web (DuckDuckGo)\n" +
    "- 📄 Find research papers (Arxiv)\n" +
    "- 📖 Look up Wikipedia\n" +
    "- 🌐 Answer from URLs you've added\n" +
    "- 📕 Answer from PDFs you've uploaded\n\n" +
    "I remember our conversation so you can ask follow-up questions naturally. Add sources in the sidebar, then ask me anything!",
};

export default function ChatPage() {
  const { sessionId } = useSession();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([WELCOME]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const [settingsChecked, setSettingsChecked] = useState(false);

  // Check if user has configured settings on mount
  useEffect(() => {
    if (user && !settingsChecked) {
      const needsSettings = !user.llm_provider || !user.llm_model || !user.has_api_key || !user.llm_base_url;
      if (needsSettings) {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-yellow-400 text-lg">⚠️</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  LLM Settings Required
                </p>
                <p className="text-xs text-gray-400">
                  Configure your provider, API key, and model to start chatting.
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate("/settings");
                }}
                className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors flex items-center gap-1"
              >
                <Settings className="w-3 h-3" />
                Configure
              </button>
            </div>
          ),
          { duration: 0 } // Persistent until dismissed
        );
      }
      setSettingsChecked(true);
    }
  }, [user, settingsChecked, navigate]);

  async function handleSend(text) {
    const userMsg = { role: "user", content: text };
    const history = messages
      .filter((m) => m.role !== "error")
      .map((m) => ({ role: m.role, content: m.content }))
      .slice(-12); // last 12 for context

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChat({
        message: text,
        model_name: user?.llm_model || "",
        provider: user?.llm_provider || "groq",
        base_url: user?.llm_base_url || "",
        memory_turns: 6,
        history,
        session_id: sessionId,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          tool_steps: res.tool_steps,
          tools_used: res.tools_used,
          answered_from_history: res.answered_from_history,
        },
      ]);
    } catch (e) {
      const detail = e?.response?.data?.detail || "";
      const errMsg =
        e?.response?.data?.detail || e.message || "Something went wrong";

      // Handle settings not configured
      if (detail === "settings_not_configured") {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-yellow-400 text-lg">⚠️</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  Settings Not Configured
                </p>
                <p className="text-xs text-gray-400">
                  Please configure your LLM provider, API key, and model in Settings.
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate("/settings");
                }}
                className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors flex items-center gap-1"
              >
                <Settings className="w-3 h-3" />
                Settings
              </button>
            </div>
          ),
          { duration: 8000 },
        );
      }
      // Handle stored key corrupted
      else if (detail === "stored_key_corrupted") {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-red-400 text-lg">🔑</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  API Key Error
                </p>
                <p className="text-xs text-gray-400">
                  Your stored API key is corrupted. Please re-enter it in Settings.
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate("/settings");
                }}
                className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors flex items-center gap-1"
              >
                <Settings className="w-3 h-3" />
                Fix Key
              </button>
            </div>
          ),
          { duration: 8000 },
        );
      }
      // Handle no API key configured
      else if (detail === "no_api_key_configured") {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-yellow-400 text-lg">⚠️</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  No API key configured
                </p>
                <p className="text-xs text-gray-400">
                  Please add your API key in Settings to start chatting.
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate("/settings");
                }}
                className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors flex items-center gap-1"
              >
                <Settings className="w-3 h-3" />
                Settings
              </button>
            </div>
          ),
          { duration: 6000 },
        );
      }
      // Handle invalid API key
      else if (detail === "invalid_api_key") {
        toast(
          (t) => (
            <div className="flex items-center gap-3">
              <span className="text-red-400 text-lg">❌</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">
                  Invalid API key
                </p>
                <p className="text-xs text-gray-400">
                  Your stored API key is invalid. Please update it in Settings.
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                  navigate("/settings");
                }}
                className="px-3 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/30 text-brand-400 hover:bg-brand-500/30 text-xs font-medium transition-colors flex items-center gap-1"
              >
                <Settings className="w-3 h-3" />
                Change Key
              </button>
            </div>
          ),
          { duration: 8000 },
        );
      } else {
        // Generic error
        toast.error(errMsg);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Error: ${errMsg}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // Determine what to show in the top bar
  const hasSettings = user?.llm_provider && user?.llm_model;
  const showModelInfo = hasSettings
    ? `${user.llm_provider} • ${user.llm_model}`
    : "Configure settings to start";

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-surface-700 shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-brand-400" />
          <span className="font-semibold text-sm text-white">
            Research Chat
          </span>
          {loading && (
            <span className="flex items-center gap-1 text-xs text-brand-400 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-400 inline-block" />
              <span
                className="w-1.5 h-1.5 rounded-full bg-brand-400 inline-block"
                style={{ animationDelay: "0.2s" }}
              />
              <span
                className="w-1.5 h-1.5 rounded-full bg-brand-400 inline-block"
                style={{ animationDelay: "0.4s" }}
              />
              thinking…
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Show configured provider/model info */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-700/50 border border-surface-600">
            <Cpu className="w-3 h-3 text-brand-400" />
            <span className={`text-xs ${hasSettings ? "text-gray-300" : "text-amber-400"}`}>
              {showModelInfo}
            </span>
          </div>
          <button
            onClick={() => {
              setMessages([WELCOME]);
              toast.success("Chat cleared");
            }}
            className="p-1.5 rounded-lg hover:bg-surface-700 text-gray-500 hover:text-red-400 transition-colors"
            title="Clear chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 max-w-4xl mx-auto w-full">
        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-surface-700 border border-surface-600 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-brand-400" />
            </div>
            <div className="bg-surface-800 border border-surface-700 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-2 h-2 rounded-full bg-brand-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} loading={loading} />
    </div>
  );
}