import React from "react";
import MasterCRUD from "./MasterCRUD";

const SionNorms = () => {
  return (
    <MasterCRUD
      endpoint="/api/masters/sion-classes/"
      title="SION Norms Management"
    />
  );
};

export default SionNorms;
