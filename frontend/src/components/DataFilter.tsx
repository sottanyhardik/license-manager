import { useState } from "react";
import { Search, Filter, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";

export default function DataFilter({ filters = [], searchFields = [], onFilterChange }) {
    const [searchTerm, setSearchTerm] = useState("");
    const [filterValues, setFilterValues] = useState({});

    const handleFilterChange = (field, value) =>
        setFilterValues((prev) => ({ ...prev, [field]: value }));

    const handleApply = () => {
        const params = { ...filterValues };
        if (searchTerm) params.search = searchTerm;
        onFilterChange(params);
    };

    const handleReset = () => {
        setSearchTerm("");
        setFilterValues({});
        onFilterChange({});
    };

    return (
        <Card className="mb-3">
            <CardContent className="pt-4">
                <h6 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                    <Filter className="size-4" />Filters
                </h6>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {searchFields.length > 0 && (
                        <div>
                            <Label className="mb-1.5">Search</Label>
                            <Input
                                placeholder={`Search by ${searchFields.join(", ")}`}
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    )}
                    {filters.map((field) => (
                        <div key={field}>
                            <Label className="mb-1.5 capitalize">{field.replace(/_/g, " ")}</Label>
                            <Input
                                placeholder={`Filter by ${field.replace(/_/g, " ")}`}
                                value={filterValues[field] || ""}
                                onChange={(e) => handleFilterChange(field, e.target.value)}
                            />
                        </div>
                    ))}
                </div>

                <div className="mt-3 flex gap-2">
                    <Button onClick={handleApply}>
                        <Search className="size-4" />Apply
                    </Button>
                    <Button variant="outline" onClick={handleReset}>
                        <X className="size-4" />Reset
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
