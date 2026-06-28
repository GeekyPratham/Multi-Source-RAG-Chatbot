import { Cpu } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

/**
 * ModelSelector - replaced by inline provider/model display in ChatPage.
 * Kept for backward compatibility, shows user's saved config read-only.
 */
export default function ModelSelector({ value, onChange }) {
  const { user } = useAuth();
  const hasSettings = user?.llm_provider && user?.llm_model;

  if (!hasSettings) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <Cpu className="w-3.5 h-3.5 text-gray-500 shrink-0" />
      <span className="text-xs text-gray-400">
        {user.llm_provider} • {user.llm_model}
      </span>
    </div>
  );
}