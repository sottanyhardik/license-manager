import React from "react";
import MasterCRUD from "../../components/MasterCRUD";

const HsnCode = () => (
  <MasterCRUD
    title="HSN Code Master"
    endpoint="masters/hs-codes/"
    fields={[
      { name: "hs_code", label: "HS Code", required: true },
      { name: "product_description", label: "Description" },
      { name: "unit_price", label: "Unit Price", type: "number" },
    ]}
  />
);

export default HsnCode;
