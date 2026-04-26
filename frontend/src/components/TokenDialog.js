import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { getToken, setToken } from "../auth";
export default function TokenDialog({ open, onClose, onSaved }) {
    const [value, setValue] = useState("");
    useEffect(() => {
        if (open)
            setValue(getToken());
    }, [open]);
    if (!open)
        return null;
    const save = () => {
        setToken(value.trim());
        onSaved?.();
        onClose();
    };
    return (_jsx("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm", onClick: onClose, children: _jsxs("div", { className: "card w-full max-w-md p-6", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { className: "text-lg font-semibold", children: "API token" }), _jsx("p", { className: "mt-1 text-sm text-slate-400", children: "Paste the bearer token configured server-side. Stored in this browser only." }), _jsx("input", { autoFocus: true, value: value, onChange: (e) => setValue(e.target.value), onKeyDown: (e) => e.key === "Enter" && save(), className: "input mt-4", placeholder: "Bearer token", type: "password" }), _jsxs("div", { className: "mt-5 flex justify-end gap-2", children: [_jsx("button", { className: "btn-ghost", onClick: onClose, children: "Cancel" }), _jsx("button", { className: "btn-ghost", onClick: () => {
                                setValue("");
                                setToken("");
                                onSaved?.();
                                onClose();
                            }, children: "Clear" }), _jsx("button", { className: "btn-primary", onClick: save, children: "Save" })] })] }) }));
}
