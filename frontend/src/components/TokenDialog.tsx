import { useEffect, useState } from "react";
import { getToken, setToken } from "../auth";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
};

export default function TokenDialog({ open, onClose, onSaved }: Props) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (open) setValue(getToken());
  }, [open]);

  if (!open) return null;

  const save = () => {
    setToken(value.trim());
    onSaved?.();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold">API token</h3>
        <p className="mt-1 text-sm text-slate-400">
          Paste the bearer token configured server-side. Stored in this browser only.
        </p>
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
          className="input mt-4"
          placeholder="Bearer token"
          type="password"
        />
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn-ghost"
            onClick={() => {
              setValue("");
              setToken("");
              onSaved?.();
              onClose();
            }}
          >
            Clear
          </button>
          <button className="btn-primary" onClick={save}>Save</button>
        </div>
      </div>
    </div>
  );
}
