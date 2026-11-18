/** Fixed allotment list rows (shape of `allotments/` list results) for parity/isolation tests. */
export const ALLOTMENT_FIXTURES = [
    {
        id: 101, invoice: "INV-101", item_name: "Crude Palm Oil", is_boe: false, is_approved: true,
        estimated_arrival_date: "12-10-2026", port_name: "Mundra", company_name: "Acme Foods",
        required_quantity: "12500.500", required_value: "1520000.75", balanced_quantity: "250.000", alloted_quantity: "12250.500", allotted_value: "1420000.75", balanced_value: "100000.00",
        allotted_items_count: 2, allocated_licenses_count: 2, dfia_list: "0310001111, 0310002222",
        allotment_details: [
            { id: 1, license_number: "0310001111", license_id: 11, serial_number: 3, product_description: "Palm Oil", qty: "10000.000", cif_fc: "12000.50", cif_inr: "1000000.00" },
            { id: 2, license_number: "0310002222", license_id: 22, serial_number: 1, product_description: "Palm Oil RBD", qty: "2250.500", cif_fc: "5000", cif_inr: "420000.75" },
        ],
    },
    {
        id: 102, invoice: "", item_name: "", is_boe: true, is_approved: false,
        estimated_arrival_date: null, port_name: "JNPT", company_name: null,
        required_quantity: 0, required_value: 0, balanced_quantity: 0,
        allotted_items_count: 1, allocated_licenses_count: 1, dfia_list: "0310003333",
        allotment_details: [
            { id: 3, license_number: "0310003333", license_id: null, serial_number: 2, product_description: "Cashew", qty: "50", cif_fc: null, cif_inr: "0" },
        ],
    },
    {
        id: 103, invoice: "INV-103", item_name: "Almonds", is_boe: false, is_approved: false,
        estimated_arrival_date: "01-01-2027", port_name: null, company_name: "Nutty Co",
        required_quantity: "99", required_value: "123456.78", balanced_quantity: "-5",
        allotted_items_count: undefined, allocated_licenses_count: undefined, dfia_list: "",
        allotment_details: [],
    },
    {
        id: 104, invoice: "INV-104", item_name: null, is_boe: true, is_approved: true,
        estimated_arrival_date: "05-05-2026", port_name: "Chennai", company_name: "Delta",
        required_quantity: "1", required_value: "10", balanced_quantity: "1",
        allotted_items_count: 0, allocated_licenses_count: 0, dfia_list: null,
        allotment_details: undefined,
    },
];
