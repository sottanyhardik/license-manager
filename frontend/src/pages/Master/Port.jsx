import React, { useState } from "react";

const Port = () => {
  const [ports, setPorts] = useState([]);
  const [portName, setPortName] = useState("");

  const addPort = (e) => {
    e.preventDefault();
    setPorts([...ports, { id: Date.now(), name: portName }]);
    setPortName("");
  };

  const deletePort = (id) => {
    setPorts(ports.filter((p) => p.id !== id));
  };

  return (
    <div>
      <h1>Port Master</h1>
      <form onSubmit={addPort}>
        <input
          type="text"
          placeholder="Enter Port Name"
          value={portName}
          onChange={(e) => setPortName(e.target.value)}
        />
        <button type="submit">Add Port</button>
      </form>

      <ul>
        {ports.map((p) => (
          <li key={p.id}>
            {p.name} <button onClick={() => deletePort(p.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Port;
