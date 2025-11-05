import React, { useState } from "react";

const SionNorms = () => {
  const [norms, setNorms] = useState([]);
  const [form, setForm] = useState({ product: "", input: "", output: "" });

  const handleSubmit = (e) => {
    e.preventDefault();
    setNorms([...norms, { id: Date.now(), ...form }]);
    setForm({ product: "", input: "", output: "" });
  };

  const handleDelete = (id) => {
    setNorms(norms.filter((n) => n.id !== id));
  };

  return (
    <div>
      <h1>SION Norms Master</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Product"
          value={form.product}
          onChange={(e) => setForm({ ...form, product: e.target.value })}
        />
        <input
          type="text"
          placeholder="Input Material"
          value={form.input}
          onChange={(e) => setForm({ ...form, input: e.target.value })}
        />
        <input
          type="text"
          placeholder="Output Quantity"
          value={form.output}
          onChange={(e) => setForm({ ...form, output: e.target.value })}
        />
        <button type="submit">Add Norm</button>
      </form>

      <ul>
        {norms.map((n) => (
          <li key={n.id}>
            {n.product} — {n.input} → {n.output}
            <button onClick={() => handleDelete(n.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default SionNorms;
