# is_restricted Field - Frontend Implementation Guide

## ✅ Automatic Switch Rendering

Good news! The `is_restricted` field will **automatically** render as a switch in the frontend without any code changes needed.

### How It Works

The `NestedFieldArray.jsx` component (lines 258-276) already has logic to automatically detect boolean fields:

```javascript
// Handle boolean fields as switch
if (field.type === "boolean" ||
    typeof fieldValue === "boolean" ||
    field.name.startsWith("is_") ||     // ← Our field matches this!
    field.name.startsWith("has_")) {

    return (
        <div className="form-check form-switch">
            <input
                type="checkbox"
                className="form-check-input"
                role="switch"
                checked={boolValue}
                onChange={(e) => handleChange(index, field.name, e.target.checked)}
            />
            <label className="form-check-label">
                {boolValue ? "Yes" : "No"}
            </label>
        </div>
    );
}
```

Since our field is named `is_restricted` (starts with `is_`), it will automatically be rendered as a switch!

## 📋 What Was Changed

### Backend Changes

1. **Added to Serializer** (`license/serializers.py` line 102):
   ```python
   fields = [..., 'is_restricted']
   ```

2. **Already in Model** (`license/models.py` line 842):
   ```python
   is_restricted = models.BooleanField(default=False, ...)
   ```

### Frontend Changes

**None needed!** The switch will automatically appear when the API returns the `is_restricted` field.

## 🎨 Visual Preview

When you edit a license import item, you'll see:

```
┌────────────────────────────────────────────────────┐
│ License Import Items                                │
├────────────────────────────────────────────────────┤
│                                                     │
│ Serial Number: [1]                                  │
│ Description: [Wheat Gluten Flour]                   │
│ Quantity: [2142253.58]                              │
│ CIF FC: [5339312.05]                                │
│                                                     │
│ Is Restricted:  ○──────○  No                       │
│                 └──────┘                            │
│                  Switch                             │
│                                                     │
│ [Save]  [Cancel]                                    │
└────────────────────────────────────────────────────┘
```

When switched ON:

```
│ Is Restricted:  ●──────●  Yes                      │
│                 └──────┘                            │
```

## 🔧 How to Use

### Setting the Field

1. **Create/Edit License**:
   - Navigate to license form
   - Scroll to import items section
   - Each import item will have an "Is Restricted" switch

2. **Toggle the Switch**:
   - **OFF (No)**: Uses license balance (shared across all items)
   - **ON (Yes)**: Uses restriction calculation from item's head (2%, 3%, 5%, 10%)

3. **Save**:
   - Click Save to persist the changes
   - The API will store the `is_restricted` value

### Business Logic

**When should you set `is_restricted = Yes`?**

- ✅ Item has a head with restriction (E1 with 2%, 3%, 5% or E5 with 10%)
- ✅ Item should calculate balance based on restriction percentage
- ✅ Item's available value should be independent of other items

**When should you keep `is_restricted = No`?**

- ✅ Item doesn't have restrictions
- ✅ Item should share the license balance with other items
- ✅ Default case for most items

## 🚀 Testing

### Test Scenario 1: New License
1. Create a new license
2. Add import items
3. Check that `is_restricted` switches appear
4. Toggle a switch ON
5. Save the license
6. Verify the value is persisted (reload the page)

### Test Scenario 2: Existing License
1. Edit an existing license
2. Navigate to import items
3. See all `is_restricted` switches (default: OFF)
4. Toggle switches as needed
5. Save changes
6. Verify balance calculations use the correct logic

### Test Scenario 3: API Response
1. Open browser DevTools → Network tab
2. Edit a license
3. Check the API response for import items
4. Verify `is_restricted` field is present:
   ```json
   {
     "id": 1,
     "serial_number": 1,
     "description": "Wheat Flour",
     "is_restricted": false,  // ← Should be present
     "balance_cif_fc": 14041.61,
     ...
   }
   ```

## 📊 Balance Calculation Flow

```
User toggles switch
       │
       ▼
Frontend sends: { is_restricted: true/false }
       │
       ▼
Backend saves to database
       │
       ▼
API returns: { is_restricted: true/false, balance_cif_fc: ... }
       │
       ▼
Frontend displays updated balance
```

### Calculation Logic

```javascript
// Pseudo-code for understanding
if (item.is_restricted) {
    // Use restriction calculation
    balance = (license.export_cif * restriction_percentage / 100)
              - (debits + allotments for this restriction)
} else {
    // Use license balance (shared)
    balance = license.balance_cif
}
```

## 🎯 Benefits

1. **Visual Clarity**: Switch makes it obvious which items are restricted
2. **Easy Toggle**: One click to change calculation method
3. **Immediate Feedback**: "Yes/No" label shows current state
4. **Automatic**: No code changes needed - works out of the box!
5. **Consistent**: Uses existing Bootstrap switch styling

## ⚙️ Advanced: Auto-Setting on Form Load

If you want to automatically set `is_restricted` based on the item's head when loading the form, you can add this logic:

```javascript
// In MasterForm.jsx or wherever the form is loaded
useEffect(() => {
    if (formData.import_license) {
        const updatedItems = formData.import_license.map(item => {
            // Check if item has restricted head
            const hasRestrictedHead = item.items?.some(i =>
                i.head?.is_restricted &&
                i.head?.restriction_percentage > 0
            );

            return {
                ...item,
                is_restricted: hasRestrictedHead
            };
        });

        setFormData({
            ...formData,
            import_license: updatedItems
        });
    }
}, [/* appropriate dependencies */]);
```

## 📝 Summary

✅ **No frontend code changes needed**
✅ Switch automatically appears for `is_restricted` field
✅ Backend already set up and ready
✅ Just run migration and start using

**The field is ready to use immediately after running the migration!**

```bash
# Run this to enable the feature:
python manage.py migrate license
```

Then refresh your frontend, and the switch will appear in the import items form! 🎉
