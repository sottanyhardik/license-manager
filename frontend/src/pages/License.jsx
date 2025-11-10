import React from "react";
import MasterCRUD from "../pages/master/MasterCRUD";

const License = () => (
    <MasterCRUD
        endpoint="/masters/license-details/"  // <-- adjust to your API route
        title="License Details"
    />
);

export default License;
