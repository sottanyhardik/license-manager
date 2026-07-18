import { toast } from "sonner";
import api from "../../../api/axios";

export interface UseMasterFormCalculationsOptions {
    entityName: string | null | undefined;
    formData: Record<string, any>;
    setFormData: React.Dispatch<React.SetStateAction<Record<string, any>>>;
    setUpdatedFields: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
    setFetchingAllotment: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useMasterFormCalculations({
    entityName,
    formData,
    setFormData,
    setUpdatedFields,
    setFetchingAllotment,
}: UseMasterFormCalculationsOptions) {
    const handleChange = async (field: string, value: any) => {
        const updates: Record<string, any> = { [field]: value };

        // Auto-calculate registration_number when license_number changes
        if (field === "license_number" && value && entityName === "licenses") {
            // Remove first character if it's a zero
            const regNumber = value.startsWith("0") ? value.substring(1) : value;
            updates.registration_number = regNumber;
        }

        // Auto-calculate registration_date when license_date changes
        if (field === "license_date" && value && entityName === "licenses") {
            updates.registration_date = value;

            // Also calculate license_expiry_date (license_date + 1 year)
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 1);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch {
                // Silently fail for date calculation errors
            }
        }

        // Auto-calculate license_expiry_date for incentive licenses (2 years from license_date)
        if (field === "license_date" && value && entityName === "incentive-licenses") {
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 2);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch {
                // Silently fail for date calculation errors
            }
        }

        // Fetch allotment details when allotment is selected in bill-of-entries
        if (field === "allotment" && entityName === "bill-of-entries") {
            // Handle both array and single value
            let allotmentIds: any[] = [];
            if (Array.isArray(value)) {
                allotmentIds = value;
            } else if (value) {
                allotmentIds = [value];
            }

            if (allotmentIds.length > 0) {
                setFetchingAllotment(true);
                try {
                    // Fetch details from all selected allotments
                    const allItemDetails: any[] = [];
                    let firstExchangeRate: any = null;
                    let firstProductName: any = null;
                    let firstPort: any = null;
                    let firstCompany: any = null;

                    for (const allotmentId of allotmentIds) {
                        const { data } = await api.get(`bill-of-entries/fetch-allotment-details/?allotment_id=${allotmentId}`);

                        // Use exchange_rate, product_name, port, and company from first allotment
                        if (!firstExchangeRate && data.exchange_rate) {
                            firstExchangeRate = data.exchange_rate;
                        }
                        if (!firstProductName && data.product_name) {
                            firstProductName = data.product_name;
                        }
                        if (!firstPort && data.port) {
                            firstPort = data.port;
                        }
                        if (!firstCompany && data.company) {
                            firstCompany = data.company;
                        }

                        // Merge all item details from all allotments
                        if (data.item_details && data.item_details.length > 0) {
                            allItemDetails.push(...data.item_details);
                        }
                    }

                    // Update form fields with fetched data
                    // Only set exchange_rate from allotment if the BOE doesn't already have one
                    const currentExcRate = parseFloat(formData.exchange_rate);
                    if (firstExchangeRate && (!currentExcRate || currentExcRate === 0)) {
                        updates.exchange_rate = firstExchangeRate;
                    }
                    if (firstProductName) {
                        updates.product_name = firstProductName;
                    }
                    if (firstPort) {
                        updates.port = firstPort;
                    }
                    if (firstCompany) {
                        updates.company = firstCompany;
                    }
                    if (allItemDetails.length > 0) {
                        // Preserve frozen (ledger-imported) rows — never overwrite them
                        const existingItems = formData.item_details || [];
                        const frozenItems = existingItems.filter((item: any) => item.is_frozen);
                        const frozenSrNumbers = new Set(frozenItems.map((item: any) => item.sr_number));
                        const filteredAllotmentItems = allItemDetails.filter((item: any) => !frozenSrNumbers.has(item.sr_number));
                        updates.item_details = [...frozenItems, ...filteredAllotmentItems];
                    } else if ((formData.item_details || []).some((item: any) => item.is_frozen)) {
                        // No new allotment items but frozen rows exist — keep them
                        updates.item_details = (formData.item_details || []).filter((item: any) => item.is_frozen);
                    }
                } catch (err: any) {
                    toast.error("Failed to fetch allotment details: " + (err.response?.data?.error || err.message));
                } finally {
                    setFetchingAllotment(false);
                }
            }
        }

        // Allotment calculations
        if (entityName === "allotments") {
            // Get current form data with the new update applied
            const currentData = { ...formData, ...updates };

            // Priority 1: Calculate cif_fc from unit_value_per_unit and required_quantity
            // Calculate whenever unit_value, quantity, or exchange_rate changes
            if ((field === "unit_value_per_unit" || field === "required_quantity" || field === "exchange_rate")
                && currentData.unit_value_per_unit && currentData.required_quantity) {
                const unitValue = parseFloat(currentData.unit_value_per_unit);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(unitValue) && !isNaN(requiredQty) && requiredQty > 0) {
                    updates.cif_fc = (unitValue * requiredQty).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation
                }
            }
            // Priority 2: If cif_fc provided but unit_value not, calculate unit_value
            else if (field === "cif_fc" && currentData.cif_fc && currentData.required_quantity && !currentData.unit_value_per_unit) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0) {
                    // Round up to 3 decimal places
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                    currentData.unit_value_per_unit = updates.unit_value_per_unit; // Update for reference
                }
            }

            // Calculate cif_fc from cif_inr and exchange_rate (if cif_inr and exchange_rate present)
            if ((field === "cif_inr" || field === "exchange_rate") && currentData.cif_inr && currentData.exchange_rate) {
                const cifInr = parseFloat(currentData.cif_inr);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifInr) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_fc = (cifInr / exchangeRate).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation

                    // Also calculate unit_value_per_unit if we have required_quantity
                    if (currentData.required_quantity) {
                        const requiredQty = parseFloat(currentData.required_quantity);
                        if (!isNaN(requiredQty) && requiredQty > 0) {
                            updates.unit_value_per_unit = (Math.ceil((parseFloat(updates.cif_fc) / requiredQty) * 1000) / 1000).toFixed(3);
                        }
                    }
                }
            }
            // Calculate cif_inr from cif_fc and exchange_rate (if cif_fc and exchange_rate present)
            else if ((field === "cif_fc" || field === "exchange_rate") && currentData.cif_fc && currentData.exchange_rate) {
                const cifFc = parseFloat(currentData.cif_fc);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifFc) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_inr = (cifFc * exchangeRate).toFixed(2);
                }
            }

            // Calculate unit_value_per_unit from cif_fc and required_quantity
            if ((field === "cif_fc" || field === "required_quantity") && currentData.cif_fc && currentData.required_quantity) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                // Only auto-calculate unit price if it's not already set or if user is changing cif_fc/quantity
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0 &&
                    (field === "cif_fc" || field === "required_quantity")) {
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                }
            }
        }

        setFormData(prev => ({
            ...prev,
            ...updates,
        }));
    };

    const handleFetchImports = async (exportIndex: number, exportItem: Record<string, any>) => {
        // Validate required fields
        if (!exportItem.norm_class) {
            toast.error("Please select a Norm Class first");
            return;
        }

        if (!exportItem.start_serial_number) {
            toast.error("Please enter Start Serial Number first");
            return;
        }

        try {
            // Fetch the SION norm class with its import items
            const { data: sionData } = await api.get(`masters/sion-classes/${exportItem.norm_class}/`);

            if (!sionData.import_norm || sionData.import_norm.length === 0) {
                toast.error("No import items found for this SION norm class");
                return;
            }

            // Get start serial number from export item (form field only, not saved)
            const startSerial = parseInt(exportItem.start_serial_number) || 0;
            const existingImports = formData.import_license || [];

            // Track existing serial numbers to prevent duplicates
            const existingSerialNumbers = new Set(existingImports.map((item: any) => item.serial_number));

            const updatedImports = [...existingImports];
            const newlyUpdatedFields: Record<string, boolean> = {};
            let addedCount = 0;
            let updatedCount = 0;

            // Process each SION import item
            sionData.import_norm.forEach((sionImport: any) => {
                const targetSerialNumber = startSerial + (sionImport.serial_number || 0);

                // Check if this serial number already exists
                const existingIndex = existingImports.findIndex((item: any) => item.serial_number === targetSerialNumber);

                if (existingIndex >= 0) {
                    // Serial number exists - only update empty fields
                    const existing = existingImports[existingIndex];
                    let fieldsUpdated = false;

                    // Update hs_code if empty
                    if (!existing.hs_code && sionImport.hsn_code) {
                        updatedImports[existingIndex].hs_code = sionImport.hsn_code;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.hs_code`] = true;
                    }

                    // Update description if empty
                    if (!existing.description && sionImport.description) {
                        updatedImports[existingIndex].description = sionImport.description;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.description`] = true;
                    }

                    // Update unit if empty
                    if (!existing.unit && sionImport.unit) {
                        updatedImports[existingIndex].unit = sionImport.unit;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.unit`] = true;
                    }

                    if (fieldsUpdated) updatedCount++;
                } else if (!existingSerialNumbers.has(targetSerialNumber)) {
                    // Serial number doesn't exist - add new item
                    const newIndex = updatedImports.length;
                    const netQty = parseFloat(exportItem.net_quantity) || 1;
                    const newItem = {
                        serial_number: targetSerialNumber,
                        hs_code: sionImport.hsn_code || null,
                        description: sionImport.description || "",
                        duty_type: sionImport.duty_type || "Basic",
                        quantity: parseFloat((netQty * (sionImport.quantity || 0)).toFixed(4)),
                        unit: sionImport.unit || "KG",
                        cif_fc: 0,
                        cif_inr: 0,
                        items: [],
                    };

                    updatedImports.push(newItem);
                    existingSerialNumbers.add(targetSerialNumber);

                    // Mark all fields as updated for new items
                    Object.keys(newItem).forEach(key => {
                        newlyUpdatedFields[`import_license.${newIndex}.${key}`] = true;
                    });

                    addedCount++;
                }
            });

            // Update form data and highlighted fields
            handleChange("import_license", updatedImports);
            setUpdatedFields(prev => ({ ...prev, ...newlyUpdatedFields }));

            const message: string[] = [];
            if (addedCount > 0) message.push(`Added ${addedCount} new import items`);
            if (updatedCount > 0) message.push(`Updated ${updatedCount} existing items`);
            if (message.length > 0) {
                toast.success(message.join('. '));
            } else {
                toast.info("No changes made");
            }

        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to fetch import items from SION");
        }
    };

    return { handleChange, handleFetchImports };
}
