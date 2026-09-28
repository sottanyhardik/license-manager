import * as React from "react";
import { Box, Stack, Typography, useTheme } from "@mui/material";

interface PageHeaderProps {
    pretitle?: React.ReactNode;
    title?: React.ReactNode;
    description?: React.ReactNode;
    actions?: React.ReactNode;
    children?: React.ReactNode;
    className?: string;
}

/**
 * MUI page header. API-compatible with the legacy PageHeader
 * (pretitle / title / description / actions) for drop-in migration.
 *
 * Design: a single, calm page-summary surface that keeps navigation, context,
 * and next actions together without competing with the working content below.
 */
export default function PageHeader({
    pretitle,
    title,
    description,
    actions,
    children,
    className,
}: PageHeaderProps) {
    const muiTheme = useTheme();

    return (
        <Box
            className={`app-page-header ${className || ""}`}
            sx={{
                mb: 3,
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: { xs: 2, sm: 2.5 },
                borderRadius: 1,
                border: `1px solid ${muiTheme.palette.divider}`,
                backgroundColor: muiTheme.palette.background.paper,
                p: { xs: 2.5, sm: 3 },
                boxShadow: muiTheme.shadows[1],
            }}
        >
            {/* Left: Breadcrumb + title + description */}
            <Box sx={{ minWidth: 0, flex: 1 }}>
                {pretitle && (
                    <Typography
                        variant="caption"
                        sx={{
                            mb: 1,
                            display: "flex",
                            alignItems: "center",
                            gap: 0.75,
                            fontWeight: 600,
                            textTransform: "uppercase",
                            letterSpacing: "0.05em",
                            color: muiTheme.palette.text.secondary,
                        }}
                    >
                        {pretitle}
                    </Typography>
                )}
                {title && (
                    <Typography
                        component="h1"
                        variant="h4"
                        sx={{
                            fontWeight: 700,
                            lineHeight: 1.2,
                            letterSpacing: "-0.01em",
                            mb: description ? 1 : 0,
                        }}
                    >
                        {title}
                    </Typography>
                )}
                {description && (
                    <Typography
                        variant="body2"
                        color="textSecondary"
                        sx={{
                            mt: 1,
                            lineHeight: 1.6,
                        }}
                    >
                        {description}
                    </Typography>
                )}
                {children}
            </Box>

            {/* Right: Actions */}
            {actions && (
                <Stack
                    direction="row"
                    spacing={{ xs: 1, sm: 1.5 }}
                    sx={{
                        flexShrink: 0,
                        flexWrap: "wrap",
                        alignItems: "center",
                    }}
                >
                    {actions}
                </Stack>
            )}
        </Box>
    );
}
