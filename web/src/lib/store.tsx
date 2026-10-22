import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useLocalState } from "./hooks";

type GameCtx = { game: string; setGame: (g: string) => void };

const Ctx = createContext<GameCtx>({ game: "ssq", setGame: () => undefined });

export function GameProvider({ children }: { children: ReactNode }) {
  const [game, setGame] = useLocalState<string>("caipiao.game", "ssq");
  const value = useMemo(() => ({ game, setGame }), [game, setGame]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useGame(): GameCtx {
  return useContext(Ctx);
}
