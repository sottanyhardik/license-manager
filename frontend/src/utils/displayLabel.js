// src/utils/displayLabel.js
// Minimal helper: prefer name/code/hsn_code/description/__str__, else empty string.
export default function getDisplayLabel(obj) {
  if (!obj) return "";
  if (typeof obj === "string") return obj;
  return (
    (obj.name && String(obj.name)) ||
    (obj.code && String(obj.code)) ||
    (obj.hsn_code && String(obj.hsn_code)) ||
    (obj.description && String(obj.description)) ||
    (obj.__str__ && String(obj.__str__)) ||
    ""
  );
}
