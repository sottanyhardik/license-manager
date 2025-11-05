import React, { useState, useEffect } from "react";
import axios from "axios";

const Company = () => {
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({ name: "", address: "" });

  useEffect(() => {
    axios.get("http://localhost:5000/api/companies") // Replace with your backend URL
      .then(res => setCompanies(res.data))
      .catch(err => console.error(err));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const res = await axios.post("http://localhost:5000/api/companies", form);
    setCompanies([...companies, res.data]);
    setForm({ name: "", address: "" });
  };

  const handleDelete = async (id) => {
    await axios.delete(`http://localhost:5000/api/companies/${id}`);
    setCompanies(companies.filter(c => c.id !== id));
  };

  return (
    <div>
      <h2>Company Master</h2>
      <form onSubmit={handleSubmit}>
        <input
          placeholder="Company Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          placeholder="Address"
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
        <button type="submit">Add</button>
      </form>

      <ul>
        {companies.map((c) => (
          <li key={c.id}>
            {c.name} - {c.address}
            <button onClick={() => handleDelete(c.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Company;
