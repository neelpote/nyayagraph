import type { Session } from "./types";

const KEY = "nyayagraph.session";
export const getSession = (): Session | null => typeof window === "undefined" ? null : JSON.parse(sessionStorage.getItem(KEY) || "null") as Session | null;
export const saveSession = (session: Session) => sessionStorage.setItem(KEY, JSON.stringify(session));
export const clearSession = () => sessionStorage.removeItem(KEY);
