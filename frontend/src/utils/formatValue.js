/**
 * formatValue.js
 * Safely formats any JS value (string, array, object) for React rendering.
 * Useful for dynamic tables like MasterCRUD.
 */
export default function formatValue(value) {
  if (Array.isArray(value)) {
    // Array of objects or primitives
    return value
      .map((v) =>
        typeof v === "object" && v !== null
          ? Object.values(v).join(" • ")
          : String(v)
      )
      .join(", ");
  }

  if (typeof value === "object" && value !== null) {
    // Single nested object
    return Object.values(value).join(" • ");
  }

  if (value === null || value === undefined || value === "") {
    return "–";
  }

  return String(value);
}
