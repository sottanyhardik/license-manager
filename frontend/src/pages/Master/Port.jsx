import React from "react";
import MasterCRUD from "../../components/MasterCRUD";

const Port = () => (
  <MasterCRUD
    title="Port Master"
    endpoint="masters/ports/"
    fields={[
      { name: "code", label: "Port Code", required: true },
      { name: "name", label: "Port Name" },
    ]}
  />
);

export default Port;
