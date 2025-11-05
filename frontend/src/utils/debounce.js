/**
 * Simple debounce utility (no dependencies)
 * Usage:
 *   import { debounce } from "../utils/debounce";
 *   const debouncedSearch = debounce((val) => { ... }, 400);
 */
export const debounce = (fn, delay = 400) => {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
};
