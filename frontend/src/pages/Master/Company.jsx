import React from "react";
import MasterCRUD from "../../components/MasterCRUD";

const Company = () => (
  <MasterCRUD
    title="Company Master"
    endpoint="masters/companies/"
    fields={[
      { name: "iec", label: "IEC Code", required: true },
      { name: "name", label: "Company Name", required: true },
      { name: "gst_number", label: "GST Number" },
      { name: "email", label: "Email", type: "email" },
      { name: "phone_number", label: "Phone" },
    ]}
  />
);

export default Company;
