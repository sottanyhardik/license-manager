import React from 'react';

interface ErrorBoundaryState { hasError: boolean; error: Error | null }
interface ErrorBoundaryProps { children: React.ReactNode }

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('Error caught by boundary:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="container mt-5">
                    <div className="alert alert-danger">
                        <h4>Something went wrong</h4>
                        <p>Please refresh the page or contact support.</p>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

export default ErrorBoundary;
