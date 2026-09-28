import { type FormEvent, useContext, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { ShieldCheck, Eye, EyeOff, Loader2, Clock, AlertCircle, Check } from "lucide-react";
import {
  Box,
  Container,
  Grid,
  Stack,
  Paper,
  Typography,
  TextField,
  InputAdornment,
  IconButton,
  Button,
  Alert,
  AlertTitle,
  Divider,
  useTheme,
  useMediaQuery,
} from "@mui/material";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { getSafeRedirect } from "../utils/authRedirect";

const CAPABILITIES = [
  "License Management",
  "Trade & Compliance Operations",
  "Planning & Reconciliation",
  "Reporting & Analytics",
];

export default function Login() {
  const { user, loading: authLoading, loginSuccess } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const reduce = useReducedMotion();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const searchParams = new URLSearchParams(location.search);
  const redirectParam = searchParams.get("redirect");
  const reason = searchParams.get("reason");
  const from =
    getSafeRedirect(location.state?.from) ??
    getSafeRedirect(redirectParam) ??
    "/dashboard";

  const sessionMessage =
    reason === "idle"
      ? "You were logged out due to inactivity."
      : reason === "session_expired"
        ? "Your session has expired. Please log in again."
        : null;

  useEffect(() => {
    document.title = "Sign In · License Manager";
  }, []);

  useEffect(() => {
    if (!authLoading && user) navigate(from, { replace: true });
  }, [user, authLoading, navigate, from]);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const { data } = await api.post("/auth/login/", form);
      loginSuccess({
        access: data.access,
        refresh: data.refresh,
        user: data.user,
      });
      navigate(from, { replace: true });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        .response?.data?.detail;
      setError(detail || "Invalid username or password.");
      setSubmitting(false);
    }
  };

  const handlePasswordToggle = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    setShowPassword((v) => !v);
  };

  return (
    <Box
      component="main"
      role="main"
      sx={{
        minHeight: "100vh",
        display: "flex",
        backgroundColor: theme.palette.mode === "light"
          ? theme.palette.background.default
          : theme.palette.background.default,
      }}
    >
      {/* Left Brand Panel — hidden on mobile */}
      {!isMobile && (
        <Box
          component="aside"
          sx={{
            width: "40%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: theme.spacing(6),
            backgroundColor:
              theme.palette.mode === "light"
                ? theme.palette.primary.main
                : theme.palette.primary.dark,
            color:
              theme.palette.mode === "light"
                ? theme.palette.primary.contrastText
                : theme.palette.primary.contrastText,
            position: "relative",
            overflow: "hidden",
            borderRight: `1px solid ${theme.palette.divider}`,
          }}
        >
          {/* Subtle geometric background */}
          <Box
            sx={{
              position: "absolute",
              inset: 0,
              backgroundImage:
                theme.palette.mode === "light"
                  ? "linear-gradient(135deg, rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(45deg, rgba(255,255,255,0.08) 1px, transparent 1px)"
                  : "linear-gradient(135deg, rgba(0,0,0,0.2) 1px, transparent 1px), linear-gradient(45deg, rgba(0,0,0,0.2) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
              pointerEvents: "none",
              opacity: 0.5,
            }}
          />

          {/* Brand Section */}
          <Box sx={{ position: "relative", zIndex: 1 }}>
            {/* Logo + Title */}
            <Stack direction="row" spacing={2} sx={{ mb: 4, alignItems: "center" }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 40,
                  height: 40,
                  borderRadius: 1,
                  border: `2px solid ${theme.palette.primary.contrastText}`,
                  opacity: 0.9,
                }}
              >
                <ShieldCheck size={20} />
              </Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  letterSpacing: "0.5px",
                  fontSize: "1.1rem",
                }}
              >
                License Manager
              </Typography>
            </Stack>

            {/* Product Statement */}
            <Typography
              variant="subtitle2"
              sx={{
                fontSize: "0.75rem",
                fontWeight: 600,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                opacity: 0.85,
                mb: 3,
              }}
            >
              Trade Operations Platform
            </Typography>

            <Typography
              variant="body1"
              sx={{
                fontSize: "1rem",
                lineHeight: 1.6,
                opacity: 0.9,
              }}
            >
              Manage licenses, BOEs, allotments, utilization and SION compliance
              from one secure workspace.
            </Typography>

            {/* Capabilities List */}
            <Stack spacing={2} sx={{ mt: 4 }}>
              {CAPABILITIES.map((capability) => (
                <Stack
                  key={capability}
                  direction="row"
                  spacing={2}
                  sx={{ alignItems: "flex-start" }}
                >
                  <Check
                    size={18}
                    style={{
                      flexShrink: 0,
                      marginTop: "2px",
                      opacity: 0.8,
                    }}
                  />
                  <Typography variant="body2" sx={{ opacity: 0.85 }}>
                    {capability}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>

          {/* Footer */}
          <Box sx={{ position: "relative", zIndex: 1 }}>
            <Divider
              sx={{
                borderColor: `rgba(${
                  theme.palette.mode === "light" ? "255,255,255" : "0,0,0"
                },0.12)`,
                mb: 2,
              }}
            />
            <Typography
              variant="caption"
              sx={{
                fontSize: "0.7rem",
                opacity: 0.6,
              }}
            >
              Secure access · Role-based permissions
            </Typography>
          </Box>
        </Box>
      )}

      {/* Right Authentication Panel */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: theme.spacing(4),
          [theme.breakpoints.down("sm")]: {
            padding: theme.spacing(2),
          },
        }}
      >
        <motion.div
          style={{
            width: "100%",
            maxWidth: "460px",
          }}
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <Stack spacing={4}>
            {/* Header */}
            <Stack spacing={1.5}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 48,
                  height: 48,
                  borderRadius: 1.5,
                  backgroundColor: theme.palette.primary.main,
                  color: theme.palette.primary.contrastText,
                }}
              >
                <ShieldCheck size={24} />
              </Box>
              <Typography
                component="h1"
                variant="h4"
                sx={{
                  fontWeight: 600,
                  fontSize: "1.75rem",
                  letterSpacing: "-0.01em",
                }}
              >
                Welcome back
              </Typography>
              <Typography
                variant="body2"
                color="textSecondary"
                sx={{
                  fontSize: "0.95rem",
                }}
              >
                Sign in to continue to License Manager
              </Typography>
            </Stack>

            {/* Alerts */}
            <Stack spacing={2}>
              {sessionMessage && (
                <Alert
                  severity="warning"
                  icon={<Clock size={20} />}
                  sx={{
                    borderRadius: 1,
                  }}
                >
                  <AlertTitle sx={{ fontWeight: 600, mb: 0.5 }}>
                    Session Notice
                  </AlertTitle>
                  {sessionMessage}
                </Alert>
              )}

              {error && (
                <Alert
                  severity="error"
                  icon={<AlertCircle size={20} />}
                  sx={{
                    borderRadius: 1,
                  }}
                >
                  <AlertTitle sx={{ fontWeight: 600, mb: 0.5 }}>
                    Sign In Failed
                  </AlertTitle>
                  {error}
                </Alert>
              )}
            </Stack>

            {/* Form */}
            <Box component="form" onSubmit={submit} noValidate>
              <Stack spacing={3}>
                {/* Username Field */}
                <TextField
                  fullWidth
                  id="login-username"
                  label="Username"
                  type="text"
                  placeholder="Enter your username"
                  autoComplete="username"
                  autoFocus
                  required
                  variant="outlined"
                  value={form.username}
                  onChange={(e) =>
                    setForm({ ...form, username: e.target.value })
                  }
                  disabled={submitting}
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      height: 48,
                      fontSize: "0.95rem",
                    },
                  }}
                />

                {/* Password Field */}
                <TextField
                  fullWidth
                  id="login-password"
                  label="Password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  variant="outlined"
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                  disabled={submitting}
                  slotProps={{
                    input: {
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            onClick={handlePasswordToggle}
                            edge="end"
                            aria-label={
                              showPassword ? "Hide password" : "Show password"
                            }
                            disabled={submitting}
                            sx={{
                              transition: "all 0.2s ease",
                            }}
                          >
                            {showPassword ? (
                              <EyeOff size={20} />
                            ) : (
                              <Eye size={20} />
                            )}
                          </IconButton>
                        </InputAdornment>
                      ),
                    },
                  }}
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      height: 48,
                      fontSize: "0.95rem",
                    },
                  }}
                />

                {/* Forgot Password Link */}
                <Box sx={{ textAlign: "right", mt: -2 }}>
                  <Link
                    to="/forgot-password"
                    style={{
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      color: theme.palette.primary.main,
                      textDecoration: "none",
                      transition: "all 0.2s ease",
                    }}
                    onMouseEnter={(e) => {
                      (e.target as HTMLElement).style.textDecoration =
                        "underline";
                      (e.target as HTMLElement).style.opacity = "0.8";
                    }}
                    onMouseLeave={(e) => {
                      (e.target as HTMLElement).style.textDecoration = "none";
                      (e.target as HTMLElement).style.opacity = "1";
                    }}
                  >
                    Forgot password?
                  </Link>
                </Box>

                {/* Sign In Button */}
                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={submitting}
                  sx={{
                    height: 48,
                    fontSize: "1rem",
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                    textTransform: "none",
                    borderRadius: 1,
                    mt: 1,
                    position: "relative",
                    transition: "all 0.2s ease",
                    "&:hover:not(:disabled)": {
                      transform: "translateY(-1px)",
                    },
                  }}
                >
                  {submitting ? (
                    <Stack
                      direction="row"
                      spacing={1}
                      sx={{ alignItems: "center", justifyContent: "center" }}
                    >
                      <Loader2
                        size={18}
                        style={{
                          animation: "spin 0.6s linear infinite",
                        }}
                      />
                      <span>Signing in…</span>
                    </Stack>
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </Stack>
            </Box>

            {/* Footer */}
            <Divider />
            <Typography
              align="center"
              variant="caption"
              color="textSecondary"
              sx={{
                fontSize: "0.75rem",
                opacity: 0.7,
              }}
            >
              License Manager · Secure sign-in
            </Typography>
          </Stack>
        </motion.div>
      </Box>

      {/* Loading spinner CSS */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Box>
  );
}
