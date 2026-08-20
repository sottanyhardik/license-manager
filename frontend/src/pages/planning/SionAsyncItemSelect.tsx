import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Select from "react-select";
import {
  fetchSionImportItem,
  searchSionImportItems,
  type ImportItemOption,
} from "@/services/api/planningRuleApi";

type SelectOption = { value: number; label: string; item: ImportItemOption };

interface SionImportItemAsyncSelectProps {
  sionId: number | null;
  value: number | null;
  onChange: (itemId: number | null, item?: ImportItemOption) => void;
  disabled?: boolean;
  error?: string;
  placeholder?: string;
  excludeIds?: number[];
}

function useDebouncedValue(value: string, delay: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function SionImportItemAsyncSelect({
  sionId,
  value,
  onChange,
  disabled = false,
  error,
  placeholder = "Search import item...",
  excludeIds = [],
}: SionImportItemAsyncSelectProps) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loadedItems, setLoadedItems] = useState<ImportItemOption[]>([]);
  const [selectedItem, setSelectedItem] = useState<ImportItemOption | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const previousSion = useRef(sionId);

  useEffect(() => {
    setSearch("");
    setPage(1);
    setLoadedItems([]);
    setSelectedItem(null);
    if (previousSion.current !== sionId && value != null) onChange(null);
    previousSion.current = sionId;
  }, [sionId, onChange, value]);

  useEffect(() => {
    setPage(1);
    setLoadedItems([]);
  }, [debouncedSearch]);

  const resultsQuery = useQuery({
    queryKey: ["sion-import-items", sionId, debouncedSearch, page],
    queryFn: () => searchSionImportItems(sionId!, debouncedSearch, page),
    enabled: Boolean(sionId),
    staleTime: 60_000,
  });
  const selectedQuery = useQuery({
    queryKey: ["sion-import-item", sionId, value],
    queryFn: () => fetchSionImportItem(sionId!, value!),
    enabled: Boolean(sionId && value),
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    const incoming = resultsQuery.data?.items;
    if (!incoming) return;
    setLoadedItems((current) => page === 1
      ? incoming
      : [...new Map([...current, ...incoming].map((item) => [item.id, item])).values()]);
  }, [resultsQuery.data, page]);

  useEffect(() => {
    if (value == null) {
      setSelectedItem(null);
      return;
    }
    if (selectedQuery.data) setSelectedItem(selectedQuery.data);
  }, [value, selectedQuery.data]);

  const excluded = useMemo(() => new Set(excludeIds), [excludeIds]);
  const resultItems = useMemo(
    () => page === 1 ? (resultsQuery.data?.items ?? []) : loadedItems,
    [page, resultsQuery.data?.items, loadedItems],
  );
  const options = useMemo<SelectOption[]>(() =>
    resultItems
      .map((item) => ({ value: item.id, label: item.name, item })),
  [resultItems]);
  const selectedOption = useMemo<SelectOption | null>(() => selectedItem && selectedItem.id === value
    ? { value: selectedItem.id, label: selectedItem.name, item: selectedItem }
    : null,
  [selectedItem, value]);

  const failed = resultsQuery.isError || selectedQuery.isError;
  const loading = resultsQuery.isFetching || selectedQuery.isFetching;

  return <div>
    <Select<SelectOption>
      isClearable
      isDisabled={disabled || !sionId}
      isLoading={loading}
      inputValue={search}
      onInputChange={(next, meta) => {
        if (meta.action === "input-change") setSearch(next);
        if (meta.action === "set-value" || meta.action === "menu-close") setSearch("");
      }}
      placeholder={!sionId ? "Select a SION first" : placeholder}
      value={selectedOption}
      options={options}
      filterOption={() => true}
      isOptionDisabled={(option) => option.value !== value && excluded.has(option.value)}
      onChange={(option) => {
        setSelectedItem(option?.item ?? null);
        setSearch("");
        onChange(option?.value ?? null, option?.item);
      }}
      onMenuScrollToBottom={() => {
        const next = resultsQuery.data?.nextPage;
        if (next && !resultsQuery.isFetching) setPage(next);
      }}
      noOptionsMessage={() => !sionId ? "Select a SION first" : failed ? "Failed to load items" : loading ? "Loading..." : "No items found"}
      loadingMessage={() => "Loading..."}
      maxMenuHeight={300}
      styles={{ control: (base) => ({ ...base, borderColor: error ? "#dc2626" : base.borderColor, minHeight: 36 }) }}
    />
    {error && <div className="mt-1 text-sm text-red-500">{error}</div>}
    {failed && <div className="mt-1 text-sm text-red-500">Failed to load items</div>}
  </div>;
}
