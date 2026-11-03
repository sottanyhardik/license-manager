/**
 * Optional (hidden-by-default) columns of the balance table. The visible set is
 * persisted to localStorage under COLUMN_STORAGE_KEY. Storage failures (private
 * mode, quota) degrade to in-memory state rather than breaking the table.
 */
import { useCallback, useEffect, useState } from "react";
import { COLUMN_STORAGE_KEY, OPTIONAL_COLUMNS, type OptionalColumnId } from "./columns";

const KNOWN_IDS: ReadonlySet<string> = new Set(OPTIONAL_COLUMNS.map((column) => column.id));

export function parseStoredColumns(raw: string | null): Set<OptionalColumnId> {
  if (!raw) return new Set();
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(
      parsed.filter((id): id is OptionalColumnId => typeof id === "string" && KNOWN_IDS.has(id)),
    );
  } catch {
    return new Set();
  }
}

function readStoredColumns(): Set<OptionalColumnId> {
  try {
    return parseStoredColumns(window.localStorage.getItem(COLUMN_STORAGE_KEY));
  } catch {
    return new Set();
  }
}

export function useOptionalColumns() {
  const [visible, setVisible] = useState<Set<OptionalColumnId>>(readStoredColumns);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify([...visible]));
    } catch {
      // Persistence is best effort; the in-memory choice still applies.
    }
  }, [visible]);

  const setColumn = useCallback((id: OptionalColumnId, on: boolean) => {
    setVisible((current) => {
      if (current.has(id) === on) return current;
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  return { visible, setColumn };
}
