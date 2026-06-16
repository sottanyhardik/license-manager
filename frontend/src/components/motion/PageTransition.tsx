import { motion, useReducedMotion } from "framer-motion";

/**
 * Wraps page content in a subtle fade/slide entrance.
 * Respects prefers-reduced-motion (renders instantly when set).
 */
export default function PageTransition({ children, className }) {
    const reduce = useReducedMotion();

    if (reduce) {
        return <div className={className}>{children}</div>;
    }

    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        >
            {children}
        </motion.div>
    );
}
