import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTheme as useMuiTheme } from "@mui/material/styles";
import { Box, Stack, Container, Button } from "@mui/material";
import { usePageTitle } from "../hooks/usePageTitle";
import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";
import Icon from "@/components/Icon";

const QUICK_ACTIONS = [
    { to: "/licenses/create",        label: "New License",   icon: "plus-circle-fill",   primary: true },
    { to: "/allotments/create",      label: "New Allotment", icon: "box-seam" },
    { to: "/bill-of-entries/create", label: "New BOE",       icon: "receipt" },
    { to: "/reports/item-pivot",     label: "Reports",       icon: "graph-up-arrow" },
];

export default function AdminLayout({ children }) {
    const navigate = useNavigate();
    const muiTheme = useMuiTheme();
    const [isInIframe] = useState(() => {
        if (typeof window === "undefined") return false;
        try { return window.self !== window.top; } catch { return true; }
    });
    usePageTitle();

    return (
        <Box
            component="div"
            className="app-shell app-shell--admin"
            sx={{
                display: "flex",
                flexDirection: "column",
                minHeight: "100vh",
                backgroundColor: muiTheme.palette.background.default,
            }}
        >
            {!isInIframe && <TopNav />}

            <Box
                component="main"
                id="main-content"
                tabIndex={-1}
                sx={{
                    flex: 1,
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                }}
            >
                <Container
                    maxWidth={false}
                    className="app-shell__content app-shell__content--admin page-enter"
                    sx={{
                        width: "100%",
                        px: isInIframe ? 2.5 : { xs: 2, sm: 3 },
                        py: isInIframe ? 2 : { xs: 2, sm: 3 },
                        flex: 1,
                        boxSizing: 'border-box',
                    }}
                >
                    {/* ARIA live region for form validation announcements */}
                    <div
                        id="form-announcements"
                        role="status"
                        aria-live="polite"
                        aria-atomic="true"
                        style={{ display: "none" }}
                    />
                    {children}
                </Container>
            </Box>

            {!isInIframe && (
                <Box
                    component="footer"
                    className="app-shell__quick-actions"
                    aria-label="Quick actions"
                    sx={{
                        position: "sticky",
                        bottom: 0,
                        zIndex: 40,
                        borderTop: `1px solid ${muiTheme.palette.divider}`,
                        backgroundColor: muiTheme.palette.background.paper,
                        backdropFilter: "blur(4px)",
                        height: 44,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        px: 2,
                    }}
                >
                    {/* Quick-create actions */}
                    <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                        {QUICK_ACTIONS.map(a => (
                            <Button
                                key={a.to}
                                type="button"
                                onClick={() => navigate(a.to)}
                                variant={a.primary ? "contained" : "outlined"}
                                color={a.primary ? "primary" : "inherit"}
                                size="small"
                                startIcon={<Icon name={a.icon} className="size-4" aria-hidden="true" />}
                                sx={{
                                    textTransform: "none",
                                    fontSize: "0.75rem",
                                    fontWeight: 600,
                                    height: 32,
                                    px: 1.5,
                                    transition: "all 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                                    "&:active": {
                                        transform: "scale(0.97)",
                                    },
                                }}
                                className="footer-action-label"
                            >
                                {a.label}
                            </Button>
                        ))}
                    </Stack>

                    {/* Subtle meta text */}
                    <Box
                        sx={{
                            display: { xs: "none", sm: "block" },
                            fontSize: "0.65rem",
                            color: muiTheme.palette.text.disabled,
                        }}
                    >
                        License Manager
                    </Box>
                </Box>
            )}

            {!isInIframe && <TaskFAB bottomOffset={44} />}
        </Box>
    );
}
