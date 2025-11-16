import {createContext, useCallback, useState} from "react";

export const ToastContext = createContext();

export const ToastProvider = ({children}) => {
    const [toasts, setToasts] = useState([]);

    const showToast = useCallback((message, type = "success", duration = 4000) => {
        const id = Date.now();
        setToasts((prev) => [...prev, {id, message, type}]);

        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, duration);
    }, []);

    const getToastIcon = (type) => {
        switch (type) {
            case "success":
                return "bi-check-circle-fill";
            case "danger":
            case "error":
                return "bi-x-circle-fill";
            case "warning":
                return "bi-exclamation-triangle-fill";
            case "info":
                return "bi-info-circle-fill";
            default:
                return "bi-check-circle-fill";
        }
    };

    const getToastClass = (type) => {
        // Map error to danger for Bootstrap classes
        if (type === "error") return "danger";
        return type;
    };

    return (
        <ToastContext.Provider value={{showToast}}>
            {children}

            <div
                className="toast-container position-fixed top-0 end-0 p-3"
                style={{zIndex: 10000}}
            >
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className={`toast align-items-center text-bg-${getToastClass(toast.type)} border-0 show fade-in-slide`}
                        role="alert"
                        aria-live="assertive"
                        aria-atomic="true"
                    >
                        <div className="d-flex">
                            <div className="toast-body d-flex align-items-center">
                                <i className={`bi ${getToastIcon(toast.type)} me-2 fs-5`}></i>
                                <span>{toast.message}</span>
                            </div>
                            <button
                                type="button"
                                className="btn-close btn-close-white me-2 m-auto"
                                onClick={() =>
                                    setToasts((prev) => prev.filter((t) => t.id !== toast.id))
                                }
                                aria-label="Close"
                            />
                        </div>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};
