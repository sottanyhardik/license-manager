import React, { useState } from "react";

const HsnCode = () => {
  const [hsnCodes, setHsnCodes] = useState([]);
  const [form, setForm] = useState({ code: "", description: "" });

  const handleSubmit = (e) => {
    e.preventDefault();
    setHsnCodes([...hsnCodes, { id: Date.now(), ...form }]);
    setForm({ code: "", description: "" });
  };

  const handleDelete = (id) => {
    setHsnCodes(hsnCodes.filter((h) => h.id !== id));
  };

  return (
    <div>
      <h1>HSN Code Master</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="HSN Code"
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
        />
        <input
          type="text"
          placeholder="Description"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <button type="submit">Add</button>
      </form>

      <ul>
        {hsnCodes.map((h) => (
          <li key={h.id}>
            {h.code} — {h.description}
            <button onClick={() => handleDelete(h.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default HsnCode;
