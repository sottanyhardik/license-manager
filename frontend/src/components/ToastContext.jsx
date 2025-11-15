import {createContext, useCallback, useState} from "react";

export const ToastContext = createContext();

export const ToastProvider = ({children}) => {
    const [toasts, setToasts] = useState([]);

    const showToast = useCallback((message, type = "success") => {
        const id = Date.now();
        setToasts((prev) => [...prev, {id, message, type}]);

        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 3000);
    }, []);

    return (
        <ToastContext.Provider value={{showToast}}>
            {children}

            <div
                className="toast-container position-fixed top-0 end-0 p-3"
                style={{zIndex: 9999}}
            >
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className={`toast align-items-center text-bg-${toast.type} show`}
                    >
                        <div className="d-flex">
                            <div className="toast-body">{toast.message}</div>
                            <button
                                type="button"
                                className="btn-close btn-close-white me-2 m-auto"
                                onClick={() =>
                                    setToasts((prev) => prev.filter((t) => t.id !== toast.id))
                                }
                            />
                        </div>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};
