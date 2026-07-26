import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Settings,
  Save,
  Loader2,
  LogOut,
  Key,
  FlaskConical,
  Sliders,
  User,
  Globe,
  Eye,
  EyeOff,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import toast from "react-hot-toast";

// Well-known providers for helpful suggestions (but user can type any)
const KNOWN_PROVIDERS = [
  { value: "groq", label: "Groq", hint: "llama-3.3-70b-versatile", needsBaseUrl: false },
  { value: "openai", label: "OpenAI", hint: "gpt-4o", needsBaseUrl: false },
  { value: "anthropic", label: "Anthropic", hint: "claude-3-5-sonnet-20241022", needsBaseUrl: true },
  { value: "deepseek", label: "DeepSeek", hint: "deepseek-chat", needsBaseUrl: false },
  { value: "mistral", label: "Mistral", hint: "mistral-small", needsBaseUrl: false },
  { value: "together", label: "Together AI", hint: "mistralai/Mixtral-8x7B-Instruct-v0.1", needsBaseUrl: false },
  { value: "openrouter", label: "OpenRouter", hint: "openai/gpt-4o", needsBaseUrl: false },
  { value: "perplexity", label: "Perplexity", hint: "llama-3-sonar-small-32k", needsBaseUrl: false },
  { value: "ollama", label: "Ollama (local)", hint: "llama3", needsBaseUrl: true },
];

export default function SettingsPage() {
  const { user, updateUser, logout } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form, setForm] = useState({
    displayName: "",
    llmProvider: "",
    llmApiKey: "",
    llmModel: "",
    temperature: 0.7,
    llmBaseUrl: "",
  });
  const [hasApiKey, setHasApiKey] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [storedApiKey, setStoredApiKey] = useState("");

  // Sync hasApiKey from user context whenever it changes
  useEffect(() => {
    setHasApiKey(!!user?.has_api_key);
  }, [user?.has_api_key]);

  useEffect(() => {
    if (user && !fetched) {
      // Get full settings from API to get base_url
      api.get("/api/settings", {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("insightagent_access_token")}`,
        },
      }).then(res => {
        const data = res.data;
        const apiKey = data.llm_api_key || "";
        setForm({
          displayName: data.display_name || user.display_name || "",
          llmProvider: data.llm_provider || "",
          llmApiKey: apiKey,
          llmModel: data.llm_model || "",
          temperature: data.temperature ?? 0.7,
          llmBaseUrl: data.llm_base_url || "",
        });
        setHasApiKey(data.has_api_key);
        setStoredApiKey(apiKey);
      }).catch(() => {
        // Fallback to user object
        setForm({
          displayName: user.display_name || "",
          llmProvider: user.llm_provider || "",
          llmApiKey: "",
          llmModel: user.llm_model || "",
          temperature: user.temperature ?? 0.7,
          llmBaseUrl: "",
        });
      }).finally(() => setFetched(true));
    }
  }, [user]);

  // Show a model hint when provider changes
  const selectedProviderHint = KNOWN_PROVIDERS.find(
    (p) => p.value === form.llmProvider
  );
  const knownProvider = KNOWN_PROVIDERS.find((p) => p.value === form.llmProvider);

  // Auto-fill base URL when provider changes (if known)
  useEffect(() => {
    if (knownProvider && !knownProvider.needsBaseUrl && !form.llmBaseUrl) {
      setForm((prev) => ({ ...prev, llmBaseUrl: "" }));
    }
  }, [form.llmProvider]);

  async function handleSave(e) {
    e.preventDefault();

    // Client-side validation
    if (!form.llmProvider.trim()) {
      toast.error("Please enter a provider name (e.g., groq, openai, deepseek)");
      return;
    }
    if (!form.llmModel.trim()) {
      toast.error("Please enter a model name");
      return;
    }
    if (!form.llmApiKey.trim() && !hasApiKey) {
      toast.error("Please enter your API key");
      return;
    }
    if (form.temperature < 0 || form.temperature > 2) {
      toast.error("Temperature must be between 0 and 2");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        display_name: form.displayName || null,
        llm_provider: form.llmProvider.trim(),
        llm_model: form.llmModel.trim(),
        temperature: form.temperature,
      };
      if (form.llmApiKey.trim()) {
        payload.llm_api_key = form.llmApiKey.trim();
      }
      if (form.llmBaseUrl.trim()) {
        payload.llm_base_url = form.llmBaseUrl.trim();
      } else {
        payload.llm_base_url = "";
      }
      const res = await api.put("/api/settings", payload, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("insightagent_access_token")}`,
        },
      });
      updateUser({
        display_name: res.data.display_name,
        llm_provider: res.data.llm_provider,
        llm_model: res.data.llm_model,
        temperature: res.data.temperature,
        has_api_key: res.data.has_api_key,
      });
      setHasApiKey(res.data.has_api_key);
      const newKey = res.data.llm_api_key || form.llmApiKey;
      setStoredApiKey(newKey);
      setForm((prev) => ({ ...prev, llmApiKey: newKey }));
      toast.success("Settings saved successfully!");
    } catch (e) {
      const detail = e?.response?.data?.detail || "Failed to save settings";
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }

  async function handleTest() {
    // Validate fields before test
    if (!form.llmProvider.trim()) {
      toast.error("Please enter a provider name first");
      return;
    }
    if (!form.llmModel.trim()) {
      toast.error("Please enter a model name first");
      return;
    }
    if (!form.llmApiKey.trim() && !hasApiKey) {
      toast.error("Please enter your API key first");
      return;
    }

    setTesting(true);
    try {
      // Send credentials to test endpoint (backend now accepts them in body)
      const testPayload = {};
      if (form.llmApiKey.trim()) {
        testPayload.llm_api_key = form.llmApiKey.trim();
      }
      if (form.llmProvider.trim()) {
        testPayload.llm_provider = form.llmProvider.trim();
      }
      if (form.llmModel.trim()) {
        testPayload.llm_model = form.llmModel.trim();
      }
      if (form.llmBaseUrl.trim()) {
        testPayload.llm_base_url = form.llmBaseUrl.trim();
      }

      const res = await api.post("/api/settings/test", testPayload, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("insightagent_access_token")}`,
        },
      });
      toast.success(res.data.message);

      // Test passed! Now save the settings to DB
      try {
        setLoading(true);
        const savePayload = {
          display_name: form.displayName || null,
          llm_provider: form.llmProvider.trim(),
          llm_model: form.llmModel.trim(),
          temperature: form.temperature,
        };
        if (form.llmApiKey.trim()) {
          savePayload.llm_api_key = form.llmApiKey.trim();
        }
        if (form.llmBaseUrl.trim()) {
          savePayload.llm_base_url = form.llmBaseUrl.trim();
        } else {
          savePayload.llm_base_url = "";
        }
        const saveRes = await api.put("/api/settings", savePayload, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("insightagent_access_token")}`,
          },
        });
        updateUser({
          display_name: saveRes.data.display_name,
          llm_provider: saveRes.data.llm_provider,
          llm_model: saveRes.data.llm_model,
          temperature: saveRes.data.temperature,
          has_api_key: saveRes.data.has_api_key,
        });
        setHasApiKey(saveRes.data.has_api_key);
        const newKey = saveRes.data.llm_api_key || form.llmApiKey;
        setStoredApiKey(newKey);
        setForm((prev) => ({ ...prev, llmApiKey: newKey }));
        toast.success("Settings saved successfully!");
      } catch (e) {
        // Test passed but save failed — still show success for test
        toast.error("Connection works, but failed to save: " + (e?.response?.data?.detail || "Unknown error"));
      } finally {
        setLoading(false);
      }
    } catch (e) {
      const detail = e?.response?.data?.detail || "Connection test failed";
      toast.error(detail);
    } finally {
      setTesting(false);
    }
  }

  async function handleLogout() {
    try {
      await api.post("/api/auth/logout", {}, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("insightagent_access_token")}`,
        },
      });
    } catch {
      // ignore
    }
    logout();
    navigate("/login");
    toast.success("Logged out");
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-700 shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <Settings className="w-5 h-5 text-brand-400" />
          <h1 className="font-bold text-white">Settings</h1>
        </div>
        <p className="text-gray-400 text-sm">
          Configure your LLM provider and preferences
        </p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl mx-auto w-full">
        <form onSubmit={handleSave} className="space-y-6">
          {/* Profile */}
          <div className="card border-surface-600">
            <div className="flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-brand-400" />
              <h2 className="font-semibold text-white text-sm">Profile</h2>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Display Name
              </label>
              <input
                type="text"
                className="input-base"
                placeholder="Your name"
                value={form.displayName}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, displayName: e.target.value }))
                }
              />
            </div>
          </div>

          {/* LLM Provider */}
          <div className="card border-surface-600">
            <div className="flex items-center gap-2 mb-4">
              <Key className="w-4 h-4 text-brand-400" />
              <h2 className="font-semibold text-white text-sm">LLM Provider</h2>
            </div>

            <div className="space-y-4">
              {/* Provider name - free text input */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Provider Name
                </label>
                <input
                  type="text"
                  className="input-base"
                  placeholder='e.g., "groq", "openai", "deepseek", or custom URL provider name'
                  value={form.llmProvider}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, llmProvider: e.target.value }))
                  }
                  list="provider-suggestions"
                />
                <datalist id="provider-suggestions">
                  {KNOWN_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value} />
                  ))}
                </datalist>
                <p className="text-xs text-gray-500 mt-1">
                  Known providers: groq, openai, anthropic, deepseek, mistral, together, openrouter, perplexity, ollama
                </p>
              </div>

              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  API Key
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? "text" : "password"}
                    className="input-base pr-10"
                    placeholder={
                      hasApiKey
                        ? "Leave blank to keep current key"
                        : "Enter your API key"
                    }
                    value={form.llmApiKey}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, llmApiKey: e.target.value }))
                    }
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey((prev) => !prev)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-white transition-colors"
                    title={showApiKey ? "Hide API key" : "Show API key"}
                  >
                    {showApiKey ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {hasApiKey
                    ? "✓ API key is set. Enter a new one to replace it."
                    : "⚠️ No API key configured. You must add one to use the chat."}
                </p>
              </div>

              {/* Model name - free text input */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Model Name
                </label>
                <input
                  type="text"
                  className="input-base"
                  placeholder={selectedProviderHint ? `e.g., ${selectedProviderHint.hint}` : "e.g., gpt-4o, llama-3.3-70b, deepseek-chat"}
                  value={form.llmModel}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, llmModel: e.target.value }))
                  }
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter any model name supported by your provider
                </p>
              </div>

              {/* Base URL (optional) */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Base URL <span className="text-gray-500">(optional)</span>
                </label>
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-gray-500 shrink-0" />
                  <input
                    type="text"
                    className="input-base"
                    placeholder={
                      knownProvider && !knownProvider.needsBaseUrl
                        ? `Auto-detected for ${form.llmProvider}`
                        : "https://api.your-provider.com/v1"
                    }
                    value={form.llmBaseUrl}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, llmBaseUrl: e.target.value }))
                    }
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {form.llmProvider
                    ? `Most providers are auto-detected. Enter a custom URL only if needed.`
                    : "Required for custom/self-hosted providers (e.g., Ollama: http://localhost:11434/v1)"}
                </p>
              </div>
            </div>
          </div>

          {/* Temperature */}
          <div className="card border-surface-600">
            <div className="flex items-center gap-2 mb-4">
              <Sliders className="w-4 h-4 text-brand-400" />
              <h2 className="font-semibold text-white text-sm">Temperature</h2>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400">Precise</span>
                <span className="text-sm font-mono text-white">
                  {form.temperature.toFixed(1)}
                </span>
                <span className="text-xs text-gray-400">Creative</span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={form.temperature}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    temperature: parseFloat(e.target.value),
                  }))
                }
                className="w-full accent-brand-500"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0.0</span>
                <span>1.0</span>
                <span>2.0</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="btn-primary flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {loading ? "Saving…" : "Save Settings"}
            </button>
            <button
              type="button"
              onClick={handleTest}
              disabled={testing || loading}
              className="btn-secondary flex items-center gap-2"
            >
              {testing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <FlaskConical className="w-4 h-4" />
              )}
              {testing ? "Testing…" : "Test Connection"}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="ml-auto p-2 rounded-lg hover:bg-surface-700 text-gray-500 hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>

          {!form.llmProvider && !form.llmModel && !hasApiKey && (
            <div className="card border-amber-500/30 bg-amber-500/5">
              <p className="text-sm text-amber-400">
                ⚠️ You need to configure a provider, API key, and model before you can use the chat.
              </p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}