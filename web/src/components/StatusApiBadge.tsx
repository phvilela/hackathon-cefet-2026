import type { StatusApi } from "../lib/api";

interface Props {
  status: StatusApi;
  usandoFallback: boolean;
}

/**
 * Selo discreto mostrado quando o recálculo pelo backend não está disponível.
 * O demo nunca quebra: mantemos o último resultado bom (ou o cenário padrão).
 */
export function StatusApiBadge({ status, usandoFallback }: Props) {
  if (status === "ok") return null;
  if (status === "carregando") {
    return (
      <span className="real-badge">
        <span className="real-dot" aria-hidden="true" />
        recalculando…
      </span>
    );
  }
  return (
    <span className="real-badge is-warn">
      <span className="real-dot" aria-hidden="true" />
      {usandoFallback
        ? "modo offline — mostrando o cenário padrão"
        : "não foi possível recalcular — mantendo o último cenário"}
    </span>
  );
}
