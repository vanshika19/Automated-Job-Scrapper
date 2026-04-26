const KEY = "jobscrapper.apiToken";
export function getToken() {
    try {
        return window.localStorage.getItem(KEY) ?? "";
    }
    catch {
        return "";
    }
}
export function setToken(token) {
    try {
        if (token)
            window.localStorage.setItem(KEY, token);
        else
            window.localStorage.removeItem(KEY);
    }
    catch {
        /* ignore */
    }
}
let unauthorizedHandler = null;
export function onUnauthorized(handler) {
    unauthorizedHandler = handler;
}
export function notifyUnauthorized() {
    unauthorizedHandler?.();
}
