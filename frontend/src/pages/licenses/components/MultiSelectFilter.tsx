import { useState, type ComponentType } from "react";
import Select, {
  components,
  type ClassNamesConfig,
  type GroupBase,
  type MultiValueProps,
  type OnChangeValue,
  type ValueContainerProps,
} from "react-select";
import type { LicenseFilterOption, OptionSourceKey, ResolvedLicenseOption } from "../useLicenseFilterOptions";
import { useDebouncedValue, useLicenseOptionSearch } from "../useLicenseFilterOptions";

export interface LicenseSelectOption {
  value: string;
  label: string;
  /** Set when the option conflicts with the opposite include/exclude filter. */
  disabledReason: string | null;
}

interface MultiSelectFilterProps {
  id: string;
  /** Visible label. Also the accessible name of the input. */
  label: string;
  source: OptionSourceKey;
  selected: ResolvedLicenseOption[];
  onChange: (values: string[]) => void;
  /** Returns the reason an option is blocked, or null when it can be chosen. */
  conflictFor?: (value: string) => string | null;
  error?: string | null;
}

const classNames: ClassNamesConfig<LicenseSelectOption, true, GroupBase<LicenseSelectOption>> = {
  control: ({ isFocused, isDisabled }) =>
    [
      "flex h-10 w-full min-w-0 items-center rounded-lg border border-input bg-card pr-1 pl-0 text-sm shadow-sm transition-[color,box-shadow,border-color]",
      "hover:border-input/80",
      isFocused ? "border-ring ring-[3px] ring-ring/30" : "",
      isDisabled ? "opacity-50" : "",
    ].join(" "),
  valueContainer: () => "flex min-w-0 flex-1 items-center gap-2 px-3",
  placeholder: () => "text-sm text-muted-foreground",
  input: () => "m-0 min-w-0 bg-transparent p-0 text-sm text-foreground outline-none",
  indicatorsContainer: () => "flex shrink-0 items-center",
  dropdownIndicator: () => "px-1 text-muted-foreground",
  menuPortal: () => "z-[60]",
  menu: () => "mt-1 overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-md",
  menuList: () => "max-h-72 overflow-y-auto p-1",
  option: ({ isFocused, isSelected, isDisabled }) =>
    [
      "flex cursor-pointer select-none items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm",
      isFocused && !isDisabled ? "bg-accent text-accent-foreground" : "",
      isSelected ? "font-medium" : "",
      isDisabled ? "cursor-not-allowed text-muted-foreground opacity-70" : "",
    ].join(" "),
  noOptionsMessage: () => "px-3 py-2 text-sm text-muted-foreground",
  loadingMessage: () => "px-3 py-2 text-sm text-muted-foreground",
};

/** Shows "N selected" in the trigger instead of one chip per value (chips render in the filter bar). */
function SelectionCountContainer(props: ValueContainerProps<LicenseSelectOption, true>) {
  const count = props.getValue().length;
  return (
    <components.ValueContainer {...props}>
      {count > 0 && <span className="whitespace-nowrap text-sm tabular-nums text-foreground">{count} selected</span>}
      {props.children}
    </components.ValueContainer>
  );
}

function HiddenMultiValue(_props: MultiValueProps<LicenseSelectOption, true>) {
  return null;
}

function toMenuOption(option: LicenseFilterOption): { value: string; label: string } {
  return { value: option.value, label: option.inactive ? `${option.label} (inactive)` : option.label };
}

/**
 * Searchable multi-select backed by a master list. Options load on the first
 * menu open and search on the server (300 ms debounce). Keyboard: arrows, Enter
 * to toggle, Backspace to remove the last, Escape to close.
 */
export function MultiSelectFilter({ id, label, source, selected, onChange, conflictFor, error }: MultiSelectFilterProps) {
  const [inputValue, setInputValue] = useState("");
  const [menuOpened, setMenuOpened] = useState(false);
  const search = useDebouncedValue(inputValue.trim());
  const optionsQuery = useLicenseOptionSearch(source, search, menuOpened);

  const selectedOptions: LicenseSelectOption[] = selected.map((item) => ({
    value: item.value,
    label: item.label,
    disabledReason: null,
  }));

  const menuOptions: LicenseSelectOption[] = (optionsQuery.data ?? []).map((option) => {
    const display = toMenuOption(option);
    return { ...display, disabledReason: conflictFor?.(option.value) ?? null };
  });

  const errorId = `${id}-error`;

  return (
    <div className="flex flex-col gap-1.5">
      <Select<LicenseSelectOption, true>
        unstyled
        styles={{ control: (base) => ({ ...base, minHeight: "var(--tb-control-height-compact)" }) }}
        inputId={id}
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        isMulti
        isSearchable
        isClearable={false}
        closeMenuOnSelect={false}
        blurInputOnSelect={false}
        placeholder="Any"
        value={selectedOptions}
        options={menuOptions}
        filterOption={null}
        inputValue={inputValue}
        isOptionDisabled={(option) => option.disabledReason !== null}
        isLoading={menuOpened && optionsQuery.isFetching}
        loadingMessage={() => "Loading…"}
        noOptionsMessage={() => {
          if (optionsQuery.isError) return "Could not load options";
          return search === "" ? "No options" : "No matches";
        }}
        formatOptionLabel={(option) => (
          <>
            <span className="truncate">{option.label}</span>
            {option.disabledReason && (
              <span className="shrink-0 text-xs text-muted-foreground">{option.disabledReason}</span>
            )}
          </>
        )}
        onMenuOpen={() => setMenuOpened(true)}
        onInputChange={(text, meta) => {
          if (meta.action === "input-change") setInputValue(text);
          else if (meta.action === "menu-close" || meta.action === "input-blur" || meta.action === "set-value") {
            setInputValue("");
          }
        }}
        onChange={(next: OnChangeValue<LicenseSelectOption, true>) => onChange(next.map((option) => option.value))}
        classNames={classNames}
        components={{
          ValueContainer: SelectionCountContainer as ComponentType<ValueContainerProps<LicenseSelectOption, true>>,
          MultiValue: HiddenMultiValue as ComponentType<MultiValueProps<LicenseSelectOption, true>>,
        }}
        menuPortalTarget={typeof document === "undefined" ? null : document.body}
        menuPosition="fixed"
      />
      {error && (
        <p id={errorId} aria-live="polite" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
